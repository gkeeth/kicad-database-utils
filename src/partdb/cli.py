#! /usr/bin/env python

import argparse
import csv
import digikey
import json

# import mouser
import os
import sys

from partdb import print_utils
from partdb.print_utils import print_message, print_error

from partdb.db import initialize_database, add_components_from_list_to_db

from partdb.component import (
    create_component_from_digikey_part,
    create_component_from_dict,
)

CONFIG_FILENAME = os.path.expanduser("~/.dblib_utils_config.json")


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


def create_component_from_digikey_pn(digikey_pn, dump_api_response=False):
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
        "--initialize-db", action="store_true", help="Initialize new, empty database."
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
        "--csv-output",
        action="store_true",
        help=(
            "Write part data to stdout, formatted as CSV. Unless otherwise "
            "specified, parts are also added to the database."
        ),
    )

    parser.add_argument(
        "--dump-api-response",
        action="store_true",
        help=(
            "Write API response object data to stdout. This can be used as a "
            "reference for implementation. Unless otherwise specified, parts "
            "are also added to the database."
        ),
    )

    parser.add_argument(
        "--use-test-database",
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

    if not (args.initialize_db or args.digikey or args.mouser or args.csv):
        print_message("Nothing to do.", verbose=True)
        sys.exit()

    if args.initialize_db:
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
