import os
import sqlite3
import sys

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
