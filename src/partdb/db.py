from collections import defaultdict
import csv
import io
import os
import sqlite3
import sys
from tabulate import tabulate

from partdb.print_utils import print_message, print_error

IPN_DUPLICATE_LIMIT = 10


class TooManyDuplicateIPNsInTableError(Exception):
    def __init__(self, IPN, table):
        self.IPN = IPN
        self.table = table


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


def add_component_to_db(con, comp, update=False, increment=False):
    """Add the given component object to a database.

    Uses the existing connection `con`. The appropriate table is selected
    automatically, and created if it does not already exist.

    Args:
        con: database connection object.
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

    Raises:
        TooManyDuplicateIPNsInTableError if there are too many duplicate IPNs
        already in the table.
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

        print_message(f"Adding component '{values['IPN']}' to table '{comp.table}'")


def get_table_names(con):
    """Return a list of table names for the connection `con`."""
    cur = con.cursor()
    res = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [t[0] for t in res.fetchall()]
    return tables


def remove_component_from_db(con, part_number):
    """Remove a component from the database by IPN, DPN1, or DPN2.

    All tables are searched. The first matching part is removed. If the first
    match corresponds to multiple components, nothing is removed.

    Args:
        con: Database connection object.
        part_number: IPN, DPN1, or DPN2 of the component to remove.
    """

    tables = get_table_names(con)
    with con:
        cur = con.cursor()
        for table in tables:
            for col in ["IPN", "DPN1", "DPN2"]:
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


def dump_database_to_dict_list(con, full=True):
    """
    Return a list of dicts of each row in the database, one dict per row.

    TODO:
    - add a table filter
    - add a column filter

    Args:
        con: database connection object.
        full: if True, dump all columns (superset of columns containing every
            column in the database). If False, dump a miinimal set of columns:
            distributor1, DPN1, distributor2, DPN2, kicad_symbol, kicad_footprint.

    Returns:
        a list of dicts, one dict per database row, each dict containing a key
        for every column in the database. The value for a key is empty if the
        key does not apply to the component in question.
    """

    minimal_cols = [
        "distributor1",
        "DPN1",
        "distributor2",
        "DPN2",
        "kicad_symbol",
        "kicad_footprint",
    ]

    def defaultdict_factory(cursor, row):
        fields = [column[0] for column in cursor.description]
        d = defaultdict(str, {field: row[n] for n, field in enumerate(fields)})
        return d

    tables = get_table_names(con)
    cur = con.cursor()
    cur.row_factory = defaultdict_factory
    rows = []
    cols = set()
    for table in tables:
        res = cur.execute(f"SELECT * FROM {table}")
        fields = [column[0] for column in res.description]
        cols.update(fields)
        for row in res:
            rows.append(row)

    if full:
        selected_cols = sorted(cols)
    else:
        selected_cols = minimal_cols

    # freeze default dict into a regular dict with consistent keys
    rows = [{k: row[k] for k in selected_cols} for row in rows]

    return rows


def dump_database_to_csv(con, full=True):
    rows = dump_database_to_dict_list(con, full)
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


def dump_database_to_table(con, full=True):
    rows = dump_database_to_dict_list(con, full)
    return tabulate(rows, headers="keys", tablefmt="simple")
