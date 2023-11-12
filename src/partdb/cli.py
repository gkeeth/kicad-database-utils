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
from partdb.print_utils import print_error, set_verbose


CONFIG_FILENAME = os.path.expanduser("~/.dblib_utils_config.json")


def print_components_from_list_as_csv(components):
    """Print all components in list to stdout, formatted as csv."""
    for comp in components:
        print(comp.to_csv())


def add_components_from_list_to_db(
    db_path, components, update=False, increment=False, no_db=False
):
    """Add all components in a list to the database.

    Args:
        db_path: Database file path.
        components: list of components to add to database.
        update: if True, when duplicate components are encountered, update
            existing components instead of attempting to create a unique
            component.
        increment: if True, when duplicate components are encountered (and if
            `update` is False), append a numeric suffix to IPN to create a
            unique IPN.
        no_db: if True, skip database operations.
    """
    if no_db:
        return
    con = db.connect_to_database(db_path)
    for comp in components:
        try:
            db.add_component_to_db(con, comp, update, increment)
        except db.TooManyDuplicateIPNsInTableError as e:
            print_error(
                f"Too many parts with IPN '{e.IPN}' already in table "
                f"'{e.table}'; skipped"
            )
    con.close()


def remove_components_from_list_from_db(db_path, part_numbers, no_db=False):
    """Remove each component in a list from the database. Components can be
    identified by IPN, DPN1, or DPN2.

    All tables are searched. For each part number, the first matching part is
    removed. If the first match corresponds to multiple components, nothing is
    removed.

    Args:
        db_path: Database file path.
        part_numbers: list of IPN, DPN1, or DPN2 for each component to remove.
        no_db: if True, skip database operations.
    """
    if no_db:
        return
    con = db.connect_to_database(db_path)
    for part_number in part_numbers:
        db.remove_component_from_db(con, part_number)
    con.close()


def print_database_to_csv_minimal(db_path):
    con = db.connect_to_database(db_path)
    print(db.dump_database_to_csv_minimal(con))
    con.close()


def print_database_to_csv_full(db_path):
    con = db.connect_to_database(db_path)
    print(db.dump_database_to_csv_full(con))
    con.close()


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
    # - mode/argument to import a minimal CSV
    # - mode/argument to import a full CSV

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
        "--dump-part-csv",
        action="store_true",
        help=(
            "Write part data for all parts being added to stdout, formatted as CSV. "
            "Unless otherwise specified, parts are also added to the database."
        ),
    )

    parser.add_argument(
        "--dump-api-response",
        action="store_true",
        help=(
            "Write API response object data for all parts being added to stdout. "
            "This can be used as a reference for implementation. "
            "Unless otherwise specified, parts are also added to the database."
        ),
    )

    parser.add_argument(
        "--dump-database-csv-full",
        action="store_true",
        help=(
            "Write all columns of all components in the database contents to stdout, "
            "formatted as CSV. "
            "The database is dumped after adding parts from the current transaction."
        ),
    )

    parser.add_argument(
        "--dump-database-csv-minimal",
        action="store_true",
        help=(
            "Write select columns of all components in the database to stdout, "
            "formatted as CSV. Included fields are: "
            "distributor1, DPN1, distributor2, DPN2, kicad_symbol, kicad_footprint. "
            "The database is dumped after adding parts from the current transaction."
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
    components = []
    args = parse_args()
    set_verbose(args.verbose)
    config_data = load_config()
    setup_digikey(config_data)
    if not args.use_test_database:
        try:
            db_path = os.path.abspath(os.path.expanduser(config_data["db"]["path"]))
        except KeyError:
            sys.exit("Error: database path not found in config file")
    else:
        db_path = os.path.abspath("test.db")

    if args.initialize_db:
        db.initialize_database(db_path)
    if args.digikey:
        digikey_pn_list = [pn.strip() for pn in args.digikey.split(",")]
        components = create_component_list_from_digikey_pn_list(
            digikey_pn_list, args.dump_api_response
        )
        db.add_components_from_list_to_db(
            db_path,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
            no_db=args.no_db,
        )
    if args.mouser:
        raise NotImplementedError
    if args.csv:
        components = create_component_list_from_csv(args.csv)
        db.add_components_from_list_to_db(
            db_path,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
            no_db=args.no_db,
        )

    if args.dump_part_csv:
        print_components_from_list_as_csv(components)

    if args.dump_database_csv_minimal:
        print_database_to_csv_minimal(db_path)

    if args.dump_database_csv_full:
        print_database_to_csv_full(db_path)


if __name__ == "__main__":
    main()
