#! /usr/bin/env python

import argparse
import csv
import digikey
import json

# import mouser
import os
import sqlite3
import sys

from partdb import print_utils
from partdb.print_utils import print_message, print_error

from partdb.component import (
    create_component_from_digikey_part,
    create_component_from_dict,
)

CONFIG_FILENAME = os.path.expanduser("~/.dblib_utils_config.json")

IPN_DUPLICATE_LIMIT = 10


"""
common columns:
    IPN
    display_name
    datasheet
    description
    keywords
    exclude_from_bom
    exclude_from_board
    kicad_symbol
    kicad_footprint
    manufacturer
    MPN
    distributor1
    DPN1
    distributor2
    DPN2

tables:
    x resistor:           value, resistance, tolerance, power, composition,
                          package
    x capacitor:          value, capacitance, tolerance, voltage, dielectric,
                          package
    inductor:             value, inductance, tolerance, package
    ferrite_bead:         impedance_at_freq, current, resistance, package
    connector:            series, circuit_configuration, gender, orientation
    x led:                  color, package
    x diode:                type, voltage, package
    transistor_bjt:       type, package
    transistor_mosfet:    type, package
    transistor_jfet:      type, package
    crystal:              frequency, load_capacitance, package
    potentiometer:        value, tolerance, power, composition, orientation
    switch:               type, configuration, orientation, current
    relay:                configuration, coil_voltage, coil_current,
                          switch_current
    x opamp:              input_type, bandwidth, package
    logic:                function, package
    x microcontroller:    pins, max_frequency, package
    x voltage_regulator:  voltage, current, package
"""


class TooManyDuplicateIPNsInTableError(Exception):
    def __init__(self, IPN, table):
        self.IPN = IPN
        self.table = table


def setup_digikey(config_data):
    """Set up environment variables and cache for digikey API calls.

    Args:
        config_data: dict of configuration data from config file.
    """
    DIGIKEY_DEFAULT_CACHE_DIR = os.path.expanduser("~/.dblib_utils_digikey_cache")

    dk_config = config_data["digikey"]
    os.environ["DIGIKEY_CLIENT_ID"] = dk_config["client_id"]
    os.environ["DIGIKEY_CLIENT_SECRET"] = dk_config["client_secret"]
    os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"

    try:
        digikey_cache_dir = os.path.expanduser(dk_config["cache_dir"])
    except KeyError:
        digikey_cache_dir = DIGIKEY_DEFAULT_CACHE_DIR

    os.environ["DIGIKEY_STORAGE_PATH"] = digikey_cache_dir
    if not os.path.isdir(digikey_cache_dir):
        os.mkdir(digikey_cache_dir)


def create_component_from_digikey_pn(digikey_pn, dump_api_response=True):
    """Create a component from a Digikey part number.

    Args:
        digikey_pn: string containing a Digikey part number
        dump_api_response: if True, print the API response object to stdout.

    Returns:
        component based on digikey_pn, or None if a component cannot be
        created from the part number.
    """
    part = digikey.product_details(digikey_pn)
    if not part:
        print_error(f"Could not get info for part {digikey_pn}")
        return None
    if dump_api_response:
        print(part)
    return create_component_from_digikey_part(part)


def create_component_list_from_digikey_pn_list(
    digikey_pn_list, dump_api_response=False
):
    """Create a list of components from a list of digikey part numbers.

    The Digikey API environment variables need to be set up before running
    this function (via setup_digikey()).

    Any part numbers that are invalid or otherwise cannot be used to create
    a component will be skipped.

    Args:
        digikey_pn_list: list of digikey part number strings.
        dump_api_response: if True, print the API response object to stdout.

    Returns:
        A list of Components corresponding to digikey part numbers.
    """

    components = []
    for pn in digikey_pn_list:
        comp = create_component_from_digikey_pn(pn, dump_api_response)
        if comp:
            components.append(comp)
        else:
            print_error(f"could not get info for part {pn}")
    return components


def create_component_list_from_csv(csv_path):
    """Create a list of components from a CSV file. Each line must contain all
    necessary fields for the component type in question.

    Any parts that are not successfully created are ignored.

    Args:
        csv_path: path to csv file to read.

    Returns:
        A list of Components corresponding to lines in the CSV file.
    """
    components = []
    with open(csv_path, "r") as infile:
        reader = csv.DictReader(infile)
        for d in reader:
            comp = create_component_from_dict(d)
            if comp:
                components.append(comp)
    return components


def initialize_database(db_path):
    """Create a new, empty database file without any tables.

    Args:
        db_path: absolute path to database.
    """
    if os.path.isfile(db_path):
        sys.exit(f"Error: {db_path} already exists and cannot be " "re-initialized.")
    con = sqlite3.connect(f"file:{db_path}", uri=True)
    con.close()


def add_component_to_db(con, comp, update=False, increment=False):
    """Add the given component object to a database.

    Uses the existing connection `con`. The appropriate table is selected
    automatically, and created if it does not already exist.

    Args:
        con: database connection to database.
        comp: Component object to add to database.
        update: When True, an existing component in the database with the
            same IPN as the new component will be updated (REPLACE'd) by the
            new component. When False, duplicate IPNs will not be added; the
            behavior in the case of duplicates depends on the value of
            `increment`.
        increment: When True, if a duplicate component (keyed by IPN) is added,
            the IPN of the new component will have a numeric suffix ('_1')
            added to avoid overwriting the existing component. If the modified
            IPN is still not unique, the suffix will be incremented (up to a
            maximum defined by IPN_DUPLICATE_LIMIT) in an attempt to create a
            unique IPN. After IPN_DUPLICATE_LIMIT unsuccessful attempts, the
            component will be skipped. When False, the IPN will not be
            incremented and any duplicate IPNs will be skipped. This argument
            is ignored when `update` is True.
    """
    insert_string, values = comp.to_sql(update)

    with con:
        cur = con.cursor()

        # Check if table exists, and create it if not.
        # We check explicitly, even though the create table string uses
        # IF NOT EXISTS, because it's nice to know when we're creating a new
        # table so we can print an info message if needed.
        res = cur.execute("SELECT name from sqlite_master")
        tables = [t[0] for t in res.fetchall()]
        if comp.table not in tables:
            print_message(f"Creating table '{comp.table}'")
            cur.execute(comp.get_create_table_string())

        # Before adding the part to the table, check if a part with the same
        # IPN is already in the table.
        res = cur.execute(f"SELECT IPN from {comp.table}")
        ipns = [t[0] for t in res.fetchall()]
        test_ipn = values["IPN"]

        if test_ipn in ipns:
            if update:
                # we're going to overwrite the existing part. This is handled
                # for us because the sql command is INSERT OR REPLACE
                print_message(
                    f"Updating existing component '{test_ipn}' in "
                    f"table '{comp.table}'"
                )
            elif increment:
                # we need to try to create a unique IPN
                for i in range(1, IPN_DUPLICATE_LIMIT):
                    test_ipn = f"{values['IPN']}_{i}"
                    if test_ipn not in ipns:
                        values["IPN"] = test_ipn
                        break
                if test_ipn != values["IPN"]:
                    # we didn't find a unique IPN
                    raise TooManyDuplicateIPNsInTableError(values["IPN"], comp.table)
            else:
                raise TooManyDuplicateIPNsInTableError(values["IPN"], comp.table)

        # add part to table, whether this is:
        # 1) The base IPN (no duplicates)
        # 2) The base IPN (duplicate, but we're replacing an existing part)
        # 3) A modified IPN with a suffix to make it unique
        cur.execute(insert_string, values)

        print_message(f"Added component '{values['IPN']}' to table " f"'{comp.table}'")


def open_connection_and_add_component_to_db(
    db_path, comp, update=False, increment=False
):
    """Open a database connection and add the given component object to the
    database.

    The database is opened and closed within this function. The appropriate
    table is selected automatically, and created if it does not already exist.

    Args:
        db_path: path to database.
        comp: Component object to add to database.
        update: when True, an existing component in the database with the
            same IPN as the new component will be updated (REPLACE'd) by the
            new component. The value of `increment` is ignored when `update` is
            True. When False, duplicate IPNs will not be added; the behavior in
            the case of duplicates depends on the value of `increment`.
        increment: When True, if a duplicate component (keyed by IPN) is added,
            the IPN of the new component will have a numeric suffix ('_1')
            added to avoid overwriting the existing component. If the modified
            IPN is still not unique, the suffix will be incremented (up to a
            maximum defined by IPN_DUPLICATE_LIMIT) in an attempt to create a
            unique IPN. After IPN_DUPLICATE_LIMIT unsuccessful attempts, the
            component will be skipped. When False, the IPN will not be
            incremented and any duplicate IPNs will be skipped. This argument
            is ignored when `update` is True.
    """

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        print_error(f"could not connect to database at path: {db_path}")
        return

    try:
        add_component_to_db(con, comp, update, increment)
    except TooManyDuplicateIPNsInTableError as e:
        print_error(
            f"Too many parts with IPN '{e.IPN}' already in table "
            f"'{e.table}'; skipped"
        )
    finally:
        con.close()


def add_components_from_list_to_db(db_path, components, update=False, increment=False):
    """Add all components in a list to the database.

    Args:
        db_path: absolute path to database.
        components: list of components to add to database.
        update: if True, when duplicate components are encountered, update
            existing components instead of attempting to create a unique
            component.
        increment: if True, when duplicate components are encountered (and if
            `update` is False), append a numeric suffix to IPN to create a
            unique IPN.
    """
    for comp in components:
        open_connection_and_add_component_to_db(db_path, comp, update, increment)


def print_components_from_list_as_csv(components):
    """Print all components in list to stdout, formatted as csv."""
    for comp in components:
        print(comp.to_csv())


def load_config():
    """Return dict containing all config data in config file."""
    with open(CONFIG_FILENAME, "r") as f:
        config_data = json.load(f)

    return config_data


def parse_args():
    """Set up CLI args and return the parsed arguments."""
    # TODO: add args for --dry-run (don't actually update database, but execute
    # everything up to db commit). Consider using a rolled-back transaction.
    parser = argparse.ArgumentParser(
        description=(
            "Add a part to the parts database, either manually or by "
            "distributor lookup."
        )
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print informational messages."
    )

    parser.add_argument(
        "--initializedb", action="store_true", help="Initialize new, empty database."
    )

    duplicates_group = parser.add_mutually_exclusive_group()
    duplicates_group.add_argument(
        "--increment-duplicates",
        "-i",
        action="store_true",
        help=(
            "If specified part already exists in database, add a new part with "
            "an incremented internal part number."
        ),
    )
    duplicates_group.add_argument(
        "--update-existing",
        "-u",
        action="store_true",
        help=(
            "If specified part already exists in database, update the existing "
            "component instead of adding a new, unique part."
        ),
    )

    parser.add_argument(
        "--no-db",
        action="store_true",
        help=(
            "Don't add part to database. This may be useful in combination "
            "with another output format, such as CSV."
        ),
    )

    parser.add_argument(
        "--csv_output",
        action="store_true",
        help=(
            "Write part data to stdout, formatted as CSV. Unless otherwise "
            "specified, parts are also added to the database."
        ),
    )

    parser.add_argument(
        "--dump_api_response",
        action="store_true",
        help=(
            "Write API response object data to stdout. This can be used as a "
            "reference for implementation. Unless otherwise specified, parts "
            "are also added to the database."
        ),
    )

    parser.add_argument(
        "--use_test_database",
        action="store_true",
        help=(
            "Use test.db in current directory instead of database specified by "
            "user configuration."
        ),
    )

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--digikey",
        "-d",
        metavar="DIGIKEY_PN",
        help=(
            "Digikey part number, or comma-separated list of part numbers, for "
            "part(s) to add to database."
        ),
    )
    source_group.add_argument(
        "--mouser",
        "-m",
        metavar="MOUSER_PN",
        help=(
            "Mouser part number, or comma-separated list of part numbers, for "
            "part(s) to add to database."
        ),
    )
    source_group.add_argument(
        "--csv",
        "-p",
        metavar="CSVFILE",
        help=(
            "CSV filename containing columns for all required part parameters. "
            "Each row is a separate part."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()
    print_utils.set_verbose(args.verbose)
    config_data = load_config()
    setup_digikey(config_data)
    if not args.use_test_database:
        try:
            db_path = os.path.abspath(os.path.expanduser(config_data["db"]["path"]))
        except KeyError:
            sys.exit("Error: database path not found in config file")
    else:
        db_path = os.path.abspath("test.db")

    if not (args.initializedb or args.digikey or args.mouser or args.csv):
        print_message("Nothing to do.", verbose=True)
        sys.exit()

    if args.initializedb:
        initialize_database(db_path)
    if args.digikey:
        digikey_pn_list = [pn.strip() for pn in args.digikey.split(",")]
        components = create_component_list_from_digikey_pn_list(
            digikey_pn_list, args.dump_api_response
        )
    if args.mouser:
        raise NotImplementedError
    if args.csv:
        components = create_component_list_from_csv(args.csv)

    if not args.no_db:
        add_components_from_list_to_db(
            db_path,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
        )

    if args.csv_output:
        print_components_from_list_as_csv(components)


if __name__ == "__main__":
    main()
