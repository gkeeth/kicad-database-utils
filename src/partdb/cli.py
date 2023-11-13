#! /usr/bin/env python

import argparse
import os
import sys

from partdb.api_helpers import (
    setup_digikey,
    create_component_list_from_csv,
    create_component_list_from_digikey_pn_list,
)
from partdb import config
from partdb import db
from partdb.print_utils import print_error, set_verbose


def get_database_path(args, config_data):
    """Determine database file path based on user configuration file and
    command line arguments (--use-test-database).
    """
    if not args.use_test_database:
        try:
            db_path = os.path.abspath(os.path.expanduser(config_data["db"]["path"]))
        except KeyError:
            sys.exit("Error: database path not found in config file")
    else:
        db_path = os.path.abspath("test.db")
    return db_path


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


def subcommand_add(args, db_path):
    components = []

    if args.digikey:
        setup_digikey(config.config_data)
        digikey_pn_list = [pn.strip() for pn in args.digikey]
        # TODO: refactor the below steps
        components = create_component_list_from_digikey_pn_list(
            digikey_pn_list, args.dump_api_response
        )
        add_components_from_list_to_db(
            db_path,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
            no_db=args.no_db,
        )

    if args.mouser:
        raise NotImplementedError

    if args.csv:
        for csvfile in args.csv:
            components += create_component_list_from_csv(csvfile.strip())
        add_components_from_list_to_db(
            db_path,
            components,
            update=args.update_existing,
            increment=args.increment_duplicates,
            no_db=args.no_db,
        )

    if args.dump_part_csv:
        print_components_from_list_as_csv(components)


def subcommand_rm(args, db_path):
    part_numbers = [pn.strip() for pn in args.rm_part_number]
    remove_components_from_list_from_db(db_path, part_numbers, no_db=False)


def parse_args(argv=None):
    """Set up CLI args and return the parsed arguments."""
    # TODO:
    # - add args for --dry-run (don't actually update database, but execute
    #   everything up to db commit). Consider using a rolled-back transaction.
    # - mode/argument for update by MPN or DPN
    # - mode/argument to import a minimal CSV
    # - mode/argument to import a full CSV
    # - instead of a test database flag, allow specifying a custom dbpath

    parser = argparse.ArgumentParser(
        description=(
            "Manage parts in the parts database. "
            "Parts can be added, removed, edited, updated, and displayed."
        )
    )
    parser.set_defaults(func=lambda _1, _2: parser.print_help())

    subparsers = parser.add_subparsers(
        title="subcommands", description="Commands for interacting with the database."
    )
    add_help = "Add part(s) to the part database."
    parser_add = subparsers.add_parser("add", description=add_help, help=add_help)
    parser_add.set_defaults(func=subcommand_add)
    group_add_source = parser_add.add_argument_group(
        "data sources", "Data source for new components"
    )
    group_add_source.add_argument(
        "--digikey",
        "-d",
        metavar="DIGIKEY_PN",
        nargs="+",
        help=("Digikey part number(s) for part(s) to add to database."),
    )
    group_add_source.add_argument(
        "--mouser",
        "-m",
        metavar="MOUSER_PN",
        nargs="+",
        help=("Mouser part number(s) for part(s) to add to database."),
    )
    group_add_source.add_argument(
        "--csv",
        "-p",
        metavar="CSVFILE",
        nargs="+",
        help=(
            "CSV filename(s) containing columns for all required part parameters. "
            "Each row is a separate part."
        ),
    )

    group_add_duplicates = parser_add.add_argument_group(
        "duplicate handling",
        "How to handle duplicate IPNs (default: skip adding the new component)",
    )
    exclusive_group_add_duplicates = group_add_duplicates.add_mutually_exclusive_group()
    exclusive_group_add_duplicates.add_argument(
        "--increment-duplicates",
        "-i",
        action="store_true",
        help=(
            "If specified part already exists in database, add a new part with "
            "an incremented internal part number."
        ),
    )
    exclusive_group_add_duplicates.add_argument(
        "--update-existing",
        "-u",
        action="store_true",
        help=(
            "If specified part already exists in database, update the existing "
            "component instead of adding a new, unique part."
        ),
    )

    parser_add.add_argument(
        "--no-db",
        action="store_true",
        help=(
            "Don't add part to database. This may be useful in combination "
            "with another output format, such as CSV."
        ),
    )

    group_add_output = parser_add.add_argument_group(
        "component data dumping", "Output control for dumping new part data to stdout"
    )
    group_add_output.add_argument(
        "--dump-part-csv",
        action="store_true",
        help=(
            "Write part data to stdout, formatted as CSV, for all parts in "
            "transaction. "
            "This action is performed in addition to the primary add transaction."
        ),
    )
    group_add_output.add_argument(
        "--dump-api-response",
        action="store_true",
        help=(
            "Write API response object data to stdout, if any, for all parts in "
            "transaction. This can be used as a reference for implementation. "
            "This action is performed in addition to the primary add transaction."
        ),
    )

    rm_help = "Remove part(s) from the part database."
    parser_rm = subparsers.add_parser("rm", description=rm_help, help=rm_help)
    parser_rm.set_defaults(func=subcommand_rm)
    parser_rm.add_argument(
        "rm_part_number",
        metavar="PART_NUMBER",
        nargs="+",
        help="Part number(s) for part(s) to remove. Can be IPN, DPN1, or DPN2.",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print informational messages."
    )

    parser.add_argument(
        "--initialize-db", action="store_true", help="Initialize new, empty database."
    )

    parser.add_argument(
        "--dump-database-csv-full",
        action="store_true",
        help=(
            "Write all columns of all components in the database to stdout, "
            "formatted as CSV. "
            "The database is dumped after completing the current transaction "
            "(e.g. add or rm)."
        ),
    )

    parser.add_argument(
        "--dump-database-csv-minimal",
        action="store_true",
        help=(
            "Write select columns of all components in the database to stdout, "
            "formatted as CSV. Included fields are: "
            "distributor1, DPN1, distributor2, DPN2, kicad_symbol, kicad_footprint. "
            "The database is dumped after completing the current transaction "
            "(e.g. add or rm)."
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

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    set_verbose(args.verbose)
    config.load_config()
    db_path = get_database_path(args, config.config_data)

    if args.initialize_db:
        db.initialize_database(db_path)

    args.func(args, db_path)

    if args.dump_database_csv_minimal:
        print_database_to_csv_minimal(db_path)

    if args.dump_database_csv_full:
        print_database_to_csv_full(db_path)


if __name__ == "__main__":
    main()
