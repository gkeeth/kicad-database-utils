#! /usr/bin/env python

import argparse
import os
import sys
from tabulate import tabulate

from partdb.api_helpers import (
    setup_digikey,
    create_component_list_from_csv,
    create_component_list_from_digikey_pn_list,
)
from partdb import config
from partdb import db
from partdb.print_utils import set_verbose


def get_database_path(args, config_data):
    """Determine database file path based on user configuration file and
    command line arguments (--database).
    """
    if args.database:
        db_path = os.path.abspath(args.database)
    else:
        try:
            db_path = os.path.abspath(os.path.expanduser(config_data["db"]["path"]))
        except KeyError:
            sys.exit("Error: database path not found in config file")
    return db_path


def print_components_from_list_as_table(components):
    """Print all components in list to stdout, formatted as a single plaintext table."""

    # we want to print as column for each part, with the first column being
    # field labels.
    # To do this, we need to transpose the dicts that we get from each component.
    # Additionally, we're organizing this as a dict of dict, where the outer dict
    # has a column per key (with key names as the column headers), and the value
    # for each key/column is a dict mapping field names to field values for that
    # component.
    rownames = {k: None for comp in components for k in comp.columns if k != "IPN"}
    cols = {"IPN": rownames.keys()}
    for comp in components:
        cols[comp.columns["IPN"]] = [comp.columns.get(k, "") for k in rownames]

    print(tabulate(cols, headers="keys", maxcolwidths=30))


def print_components_from_list_as_csv(components):
    """Print all components in list to stdout, each formatted as a separate CSV
    table.
    """
    for comp in components:
        print(comp.to_csv())


def add_components_from_list_to_db(db_path, components, no_db=False, update=None):
    """Add all components in a list to the database.

    Each component is updated so that its IPN matches the one assigned to it in
    the database.

    Args:
        db_path: Database file path.
        components: list of components to add to database.
        no_db: if True, skip database operations.
        update:
            if None, a new component is added to the database. If a valid IPN,
                that component is updated instead of adding a new component. If
                an invalid IPN (IPN not in database), return with an error.
    """
    if no_db:
        return
    con = db.connect_to_database(db_path)
    if not con:
        return
    for comp in components:
        IPN = db.add_component_to_db(con, comp, update)
        comp.columns["IPN"] = IPN
    con.close()


def remove_components_from_list_from_db(db_path, part_numbers, no_db=False):
    """Remove each component in a list from the database. Components can be
    identified by IPN, MPN, DPN1, or DPN2.

    All tables are searched. For each part number, the first matching part is
    removed. If the first match corresponds to multiple components, nothing is
    removed.

    Args:
        db_path: Database file path.
        part_numbers: list of IPN, MPN, DPN1, or DPN2 for each component to remove.
        no_db: if True, skip database operations.
    """
    if no_db:
        return
    con = db.connect_to_database(db_path)
    if not con:
        return
    for part_number in part_numbers:
        db.remove_component_from_db(con, part_number)
    con.close()


def subcommand_init(args):
    if not (args.config or args.database):
        args.add_parser.error("no initialization target provided (--config/--database)")
    if not args.database:
        args.database = ""
    if args.config:
        config.make_config_file(config_path=args.config, db_path=args.database)
    if args.database:
        db.initialize_database(args.database)


def subcommand_add(args):
    components = []

    if not (args.digikey or args.mouser or args.csv):
        args.add_parser.error(
            "no component information source provided (--digikey/--mouser/--csv)"
        )

    config.load_config(args.config)
    db_path = get_database_path(args, config.config_data)

    if args.digikey:
        setup_digikey(config.config_data)
        digikey_pn_list = [pn.strip() for pn in args.digikey]
        components += create_component_list_from_digikey_pn_list(
            digikey_pn_list, args.show_api_response
        )

    if args.mouser:
        raise NotImplementedError

    if args.csv:
        for csvfile in args.csv:
            components += create_component_list_from_csv(csvfile.strip())

    add_components_from_list_to_db(
        db_path, components, no_db=args.no_db, update=args.update
    )

    if args.show:
        print_components_from_list_as_table(components)

    if args.show_csv:
        print_components_from_list_as_csv(components)


def subcommand_rm(args):
    config.load_config(args.config)
    db_path = get_database_path(args, config.config_data)
    part_numbers = [pn.strip() for pn in args.rm_part_number]
    remove_components_from_list_from_db(db_path, part_numbers, no_db=False)


def subcommand_show(args):
    config.load_config(args.config)
    db_path = get_database_path(args, config.config_data)
    con = db.connect_to_database(db_path)
    if not con:
        return

    if args.columns:
        columns = args.columns
    elif args.minimal_columns:
        columns = db.minimal_columns
    else:
        columns = []  # all columns

    if args.table_names_only:
        for table in db.get_table_names(con):
            print(table)
    else:
        if args.csv:
            dump = db.dump_database_to_csv(con, args.tables, columns)
        else:
            dump = db.dump_database_to_table(con, args.tables, columns)
        if dump:
            print(dump)

    con.close()


def _parse_init_args(subparsers):
    init_help = "initialize part database and/or configuration file"
    parser_init = subparsers.add_parser("init", description=init_help, help=init_help)
    parser_init.set_defaults(func=subcommand_init)
    group_init_files = parser_init.add_argument_group(
        "initialization targets", "files to initialize; at least one must be provided"
    )
    group_init_files.add_argument(
        "--config",
        metavar="CONFIG_FILE_PATH",
        nargs="?",
        const=config.DEFAULT_CONFIG_PATH,
        help=(
            "create a template configuration file at the specified path, "
            "or the default if no path is given. "
            "Database path is taken from --database arg, if provided. "
            "Some config values must be filled in manually"
        ),
    )
    group_init_files.add_argument(
        "--database",
        metavar="DATABASE_FILE_PATH",
        help="create a new, empty database at the specified path",
    )


def _parse_add_args(subparsers):
    add_help = "add component(s) to the part database"
    parser_add = subparsers.add_parser("add", description=add_help, help=add_help)
    parser_add.set_defaults(func=subcommand_add)
    group_add_source = parser_add.add_argument_group(
        "data sources", "data source for new components; at least one must be provided"
    )
    group_add_source.add_argument(
        "--digikey",
        "-d",
        metavar="DIGIKEY_PN",
        nargs="+",
        help="Digikey part number(s) for component(s) to add to database",
    )
    group_add_source.add_argument(
        "--mouser",
        "-m",
        metavar="MOUSER_PN",
        nargs="+",
        help="Mouser part number(s) for component(s) to add to database.",
    )
    group_add_source.add_argument(
        "--csv",
        "-p",
        metavar="CSVFILE",
        nargs="+",
        help=(
            "CSV filename(s) containing columns for all required component parameters; "
            "each row is a separate component"
        ),
    )

    parser_add.add_argument(
        "--no-db",
        action="store_true",
        help="create new component but do not it to the database",
    )
    parser_add.add_argument(
        "--update",
        metavar="IPN",
        help="update existing component IPN instead of adding a new component",
    )

    group_add_output = parser_add.add_argument_group(
        "component data display",
        "output control for printing new component data to stdout",
    )
    group_add_output.add_argument(
        "--show",
        action="store_true",
        help=(
            "show component data for all new components, "
            "formatted as a single plaintext table"
        ),
    )
    group_add_output.add_argument(
        "--show-csv",
        action="store_true",
        help=(
            "show component data for all new components, "
            "formatted as a separate CSV table for each component"
        ),
    )
    group_add_output.add_argument(
        "--show-api-response",
        action="store_true",
        help="show API response data, if any, for all new components",
    )

    return parser_add


def _parse_rm_args(subparsers):
    rm_help = "remove component(s) from the part database"
    parser_rm = subparsers.add_parser("rm", description=rm_help, help=rm_help)
    parser_rm.set_defaults(func=subcommand_rm)
    parser_rm.add_argument(
        "rm_part_number",
        metavar="PART_NUMBER",
        nargs="+",
        help="part number(s) for component(s) to remove (IPN, MPN, DPN1, or DPN2)",
    )

    return parser_rm


def _parse_show_args(subparsers):
    show_help = "show contents of part database"
    parser_show = subparsers.add_parser("show", description=show_help, help=show_help)
    parser_show.set_defaults(func=subcommand_show)
    parser_show.add_argument(
        "--tables",
        metavar="TABLE_NAME",
        nargs="+",
        help=(
            "display the specified table(s); "
            "if this argument is not given, all tables are shown"
        ),
    )
    group_show_column_filters = parser_show.add_argument_group(
        "output columns", "database columns to show"
    )
    exclusive_group_show_column_filters = (
        group_show_column_filters.add_mutually_exclusive_group()
    )
    exclusive_group_show_column_filters.add_argument(
        "--all-columns",
        action="store_true",
        help="display all columns for all components being printed (default).",
    )
    exclusive_group_show_column_filters.add_argument(
        "--minimal-columns",
        action="store_true",
        help=(
            "display a minimal set of columns: "
            "distributor1, DPN1, distributor2, DPN2, kicad_symbol, and kicad_footprint"
        ),
    )
    exclusive_group_show_column_filters.add_argument(
        "--columns",
        metavar="COLUMN_NAME",
        nargs="+",
        help="display the specified column(s)",
    )
    exclusive_group_show_column_filters.add_argument(
        "--table-names-only",
        action="store_true",
        help=(
            "only display table names, not the components or columns in each table "
            "(the output format argument is ignored)"
        ),
    )
    group_show_format = parser_show.add_argument_group(
        "output format", "format of printed output"
    )
    exclusive_group_show_format = group_show_format.add_mutually_exclusive_group()
    exclusive_group_show_format.add_argument(
        "--tabular", action="store_true", help="print in tabular format (default)"
    )
    exclusive_group_show_format.add_argument(
        "--csv", action="store_true", help="print in CSV format"
    )

    return parser_show


def parse_args(argv=None):
    """Set up CLI args and return the parsed arguments."""
    # TODO:
    # - display shows parts that we skipped; we may not want to show skipped parts
    # - add --digikey/--mouser args can be filenames, not just part numbers
    # - preview argument (synonym for --no-db --show)
    # - mode/argument to import a minimal CSV
    # - filter show by IPN (or arbitrary fields, key-value pairs)?

    parser = argparse.ArgumentParser(
        description=(
            "Manage components in the parts database. "
            "Components can be added, updated, removed, and displayed."
        )
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subparsers = parser.add_subparsers(
        title="subcommands", description="edit and explore the parts database"
    )

    parser_init = _parse_init_args(subparsers)
    parser_add = _parse_add_args(subparsers)
    parser_rm = _parse_rm_args(subparsers)
    parser_show = _parse_show_args(subparsers)

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="print informational messages"
    )
    parser.add_argument(
        "--config",
        metavar="CONFIG_PATH",
        help="use configuration file at CONFIG_PATH instead of default location",
    )
    parser.add_argument(
        "--database",
        metavar="DATABASE_PATH",
        help=(
            "use DATABASE_PATH instead of the database specified by "
            "user configuration"
        ),
    )

    # define a custom namespace that contains references to the parsers, so
    # we can later add parser error messages from within subcommands
    class ArgContext(argparse.Namespace):
        top_parser = parser
        add_parser = parser_add
        rm_parser = parser_rm
        show_parser = parser_show
        init_parser = parser_init

    arg_context = ArgContext()

    return parser.parse_args(argv, namespace=arg_context)


def main(argv=None):
    args = parse_args(argv)
    set_verbose(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
