#! /usr/bin/env python

import argparse
import json

import os
import sys

from partdb.api_helpers import (
    setup_digikey,
    create_component_list_from_csv,
    create_component_list_from_digikey_pn_list,
)
from partdb import db
from partdb import print_utils
from partdb.print_utils import print_message


CONFIG_FILENAME = os.path.expanduser("~/.dblib_utils_config.json")


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
    # TODO:
    # - add args for --dry-run (don't actually update database, but execute
    #   everything up to db commit). Consider using a rolled-back transaction.
    # - mode/argument for update by MPN or DPN
    # - mode/argument to remove part by IPN (or maybe MPN and/or DPN)
    # - mode/argument to dump a list (CSV?) of table, DPN, symbol, footprint

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
        db.initialize_database(db_path)
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
        con = db.connect_to_database(db_path)
        db.add_components_from_list_to_db(
            con,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
        )
        con.close()

    if args.csv_output:
        print_components_from_list_as_csv(components)


if __name__ == "__main__":
    main()
