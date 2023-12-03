from collections import defaultdict
import csv
import io
import os
import re
import sqlite3
import sys
from tabulate import tabulate

from partdb.print_utils import print_message, print_error

minimal_columns = [
    "distributor1",
    "DPN1",
    "distributor2",
    "DPN2",
    "kicad_symbol",
    "kicad_footprint",
]


def initialize_database(db_path):
    """Create a new, empty database file without any tables.

    Args:
        db_path: absolute path to database.
    """
    if os.path.isfile(db_path):
        sys.exit(f"Error: {db_path} already exists and cannot be re-initialized.")
    con = sqlite3.connect(f"file:{db_path}", uri=True)
    con.close()


def connect_to_database(db_path):
    """Connect to a database at `db_path` and return the connection object."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        print_error(f"could not connect to database at path: {db_path}")
        return
    return con


def add_component_to_db(con, comp, update=None):
    """Add the given component object to a database if it is not already in
    the database.

    Uses the existing connection `con`. The appropriate table is selected
    automatically, and created if it does not already exist.

    Args:
        con: database connection object.
        comp: Component object to add to database.
        update:
            if None, a new component is added to the database. If a valid IPN,
                that component is updated instead of adding a new component. If
                an invalid IPN (IPN not in database), return with an error.
    Returns:
        the IPN assigned to the component in the database, or None if the
        component was not added.
    """
    insert_string, values = comp.to_sql(update)
    tables = get_table_names(con)

    with con:
        cur = con.cursor()

        # Check if table exists, and create it if not.
        # We check explicitly, even though the create table string uses
        # IF NOT EXISTS, because it's nice to know when we're creating a new
        # table so we can print an info message if needed.
        if comp.table not in tables:
            print_message(f"Creating table '{comp.table}'")
            cur.execute(comp.get_create_table_string())

        # Before adding the part to the table, we need to choose an IPN for it
        if not update:
            if comp.already_in_db(con):
                print_error(f"component already in table '{comp.table}'")
                return None
            prefix = re.match(r"([A-Z]+)\d*", values["IPN"]).group(1)
            res = cur.execute(
                f"SELECT IPN FROM {comp.table} WHERE IPN LIKE '{prefix}%'"
            )
            ipns = sorted([t[0] for t in res.fetchall()])
            if ipns:
                highest_ipn = ipns[-1]
                highest_number = re.match(rf"{prefix}(\d+)", highest_ipn).group(1)
            else:
                highest_number = 0
            values["IPN"] = f"{prefix}{int(highest_number) + 1:0>4}"
        else:
            res = cur.execute(
                f"SELECT IPN FROM {comp.table} WHERE IPN = ?", (update,)
            ).fetchall()
            if not res:
                print_error(f"component '{update}' not in table '{comp.table}'")
                return None
            values["IPN"] = update

        cur.execute(insert_string, values)

        print_message(f"Adding component '{values['IPN']}' to table '{comp.table}'")
        return values["IPN"]


def get_table_names(con):
    """Return a list of table names for the connection `con`."""
    cur = con.cursor()
    res = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [t[0] for t in res.fetchall()]
    return tables


def remove_component_from_db(con, part_number):
    """Remove a component from the database by IPN, MPN, DPN1, or DPN2.

    All tables are searched. The first matching part is removed. If the first
    match corresponds to multiple components, nothing is removed.

    Args:
        con: Database connection object.
        part_number: IPN, MPN, DPN1, or DPN2 of the component to remove.
    """

    tables = get_table_names(con)
    with con:
        cur = con.cursor()
        for table in tables:
            for col in ["IPN", "MPN", "DPN1", "DPN2"]:
                res = cur.execute(
                    f"SELECT IPN FROM {table} WHERE {col} = '{part_number}'"
                ).fetchall()
                if len(res) == 1:
                    cur.execute(f"DELETE FROM {table} WHERE {col} = '{part_number}'")
                    print_message(
                        f"Removing component '{res[0][0]}' from table '{table}'"
                    )
                    return
                if len(res) > 1:
                    IPNs = ", ".join(f"'{c[0]}'" for c in res)
                    print_message(
                        f"Multiple components with {col}=='{part_number}' "
                        f"in table '{table}' ({IPNs}); skipping"
                    )
                    return
    print_message(f"No component matching '{part_number}' found")


def dump_database_to_dict_list(con, tables, columns=[]):
    """
    Return a list of dicts of each row in the database, one dict per row.

    Args:
        con: database connection object.
        tables: tables to dump. If Falsy, all tables are dumped.
        columns: list of columns to print. If a column doesn't exist in any of
            the searched tables, an error is printed. If Falsy, all columns are
            printed.

    Returns:
        a list of dicts, one dict per database row, each dict containing a key
        for every column in `columns`. The value for a key is empty if the
        key does not apply to the component in question.
    """

    def defaultdict_factory(cursor, row):
        fields = [column[0] for column in cursor.description]
        d = defaultdict(str, {field: row[n] for n, field in enumerate(fields)})
        return d

    tables_in_database = set(get_table_names(con))
    if tables:
        invalid_tables = set(tables).difference(tables_in_database)
        if invalid_tables:
            print_error(f"skipping nonexistent tables: {', '.join(invalid_tables)}")
        tables = tables_in_database.intersection(tables)
    else:  # all tables
        tables = tables_in_database

    cur = con.cursor()
    cur.row_factory = defaultdict_factory
    rows = []
    cols_in_database = set()
    for table in sorted(tables):
        res = cur.execute(f"SELECT * FROM {table}")
        fields = [column[0] for column in res.description]
        cols_in_database.update(fields)
        for row in res:
            rows.append(row)

    if columns:
        invalid_columns = set(columns).difference(cols_in_database)
        if invalid_columns:
            print_error(f"skipping nonexistent columns: {', '.join(invalid_columns)}")
        # set intersection, but preserve specified column order
        columns = [col for col in columns if col in cols_in_database]
    else:  # all columns
        columns = sorted(cols_in_database)

    # freeze default dict into a regular dict with consistent keys
    rows = [{k: row[k] for k in columns} for row in rows]

    return rows


def dump_database_to_csv(con, tables, columns=[]):
    """
    Return a CSV string, with a header row and one row per row in the database.

    Args:
        con: database connection object.
        tables: tables to dump. If Falsy, all tables are dumped.
        columns: list of columns to print. If a column doesn't exist in any of
            the searched tables, an error is printed. If Falsy, all columns are
            printed.

    Returns:
        a CSV string, with a header row and a value row for each row in the
        secified tables. There is a column for every column in `columns`. The
        value in a column will be empty if the column does not exist for the
        component in question.
    """
    rows = dump_database_to_dict_list(con, tables, columns)
    if not rows:  # don't crash on empty database
        return ""

    with io.StringIO() as csv_string:
        csvwriter = csv.DictWriter(
            csv_string, fieldnames=rows[0].keys(), extrasaction="ignore"
        )
        csvwriter.writeheader()
        for row in rows:
            csvwriter.writerow(row)
        return csv_string.getvalue().strip()


def dump_database_to_table(con, tables, columns=[]):
    """
    Return a string containing a plaintext table, with a header row and one row
    per row in the database.

    Args:
        con: database connection object.
        tables: tables to dump. If Falsy, all tables are dumped.
        columns: list of columns to print. If a column doesn't exist in any of
            the searched tables, an error is printed. If Falsy, all columns are
            printed.

    Returns:
        a plaintext table, with a header row and a value row for each row in the
        secified tables. There is a column for every column in `columns`. The
        value in a column will be empty if the column does not exist for the
        component in question.
    """
    rows = dump_database_to_dict_list(con, tables, columns)
    return tabulate(rows, headers="keys", tablefmt="simple")
