#! /usr/bin/env python

import sys
import os
import io
import re
from abc import ABC, abstractmethod
from collections import OrderedDict
import argparse
import sqlite3
import csv
import json
import digikey
import mouser

CONFIG_FILENAME = os.path.expanduser("~/.dblib_add_part_config.json")

IPN_DUPLICATE_LIMIT = 10

VERBOSE = False


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
    resistor:             value, resistance, tolerance, power, composition, package
    capacitor:            value, capacitance, tolerance, voltage, dielectric, package
    inductor:             value, inductance, tolerance, package
    ferrite_bead:         impedance_at_freq, current, resistance, package
    connector:            series, circuit_configuration, gender, orientation
    led:                  color, package
    diode:                type, voltage, package
    transistor_bjt:       type, package
    transistor_mosfet:    type, package
    transistor_jfet:      type, package
    crystal:              frequency, load_capacitance, package
    potentiometer:        value, tolerance, power, composition, orientation
    switch:               type, configuration, orientation, current
    relay:                configuration, coil_voltage, coil_current, switch_current
    opamp:                input_type, bandwidth, package
    logic:                function, package
    microcontroller:      pins, max_frequency, package
    voltage_regulator:    voltage, current, package
"""


class PartInfoNotFoundError(Exception):
    pass


class TooManyDuplicateIPNsInTableError(Exception):
    def __init__(self, IPN, table):
        self.IPN = IPN
        self.table = table


def print_message(message):
    """Print a message to stdout if global variable VERBOSE is True."""
    if VERBOSE:
        print(message)


def print_error(message):
    """Print a message to stderr, with "ERROR: " prepended."""
    print(f"Error: {message}")


class Component(ABC):
    primary_key = "IPN"

    def __init__(self, IPN, datasheet, description, keywords, value,
                 kicad_symbol, kicad_footprint, manufacturer, MPN,
                 distributor1, DPN1, distributor2, DPN2,
                 exclude_from_bom=0, exclude_from_board=0):
        # columns that all types of components need. Many of these map onto
        # KiCad builtin fields or properties.
        self.columns = OrderedDict()
        self.columns[self.primary_key] = IPN  # unique ID for component
        self.columns["datasheet"] = datasheet
        self.columns["description"] = description
        self.columns["keywords"] = keywords
        self.columns["value"] = value
        self.columns["exclude_from_bom"] = int(exclude_from_bom)
        self.columns["exclude_from_board"] = int(exclude_from_board)
        self.columns["kicad_symbol"] = kicad_symbol
        self.columns["kicad_footprint"] = kicad_footprint
        self.columns["manufacturer"] = manufacturer
        self.columns["MPN"] = MPN
        self.columns["distributor1"] = distributor1
        self.columns["DPN1"] = DPN1
        self.columns["distributor2"] = distributor2
        self.columns["DPN2"] = DPN2

    @classmethod
    @abstractmethod
    def from_digikey(cls, digikey_part):
        """Construct a component from a digikey part object.

        Returns:
            The constructed component. If the component cannot be constructed
            for any reason, return None.
        """
        raise NotImplementedError

    @classmethod
    def get_digikey_common_data(cls, digikey_part):
        """Return a dict of the common data from a digikey part object."""
        common_data = {
                "datasheet":            digikey_part.primary_datasheet,
                "manufacturer":         digikey_part.manufacturer.value,
                "MPN":                  digikey_part.manufacturer_part_number,
                "distributor1":         "Digikey",
                "DPN1":                 digikey_part.digi_key_part_number,
                "distributor2":         "",
                "DPN2":                 "",
                }
        return common_data

    def get_create_table_string(self):
        """Return a sqlite string to create a table for the component type."""
        column_defs = [column + " PRIMARY KEY" if column == self.primary_key
                       else column
                       for column in self.columns.keys()]
        column_defs = ", ".join(column_defs)
        return f"CREATE TABLE IF NOT EXISTS {self.table}({column_defs})"

    def to_sql(self, update=False):
        """Create a SQL command string that will insert the component into the
        database.

        Args:
            update: when True, the generated SQL command will cause duplicate
                rows already in the database to be updated (REPLACE'd) on
                INSERT.  When False, the generated SQL command will not REPLACE
                any existing row with the same key; instead sqlite will
                generate an error.

        Returns:
            A tuple (insert string, column data) of the parameterized SQL
            insert string and the dict of values to populate the insert string
            with.
        """
        column_names = self.columns.keys()
        column_keys = ":" + ", :".join(column_names)
        command = "INSERT OR REPLACE" if update else "INSERT"
        insert_string = f"{command} INTO {self.table} VALUES({column_keys})"
        return (insert_string, self.columns)

    def to_csv(self, header=True):
        """Create a string containing the component data, formatted as CSV.

        Args:
            header: if True, also print a header row containing column names

        Returns:
            A string containing a CSV representation of the component. If
            `header` is true, the string is a multi-line string containing
            a header row followed by a data row.
        """

        with io.StringIO() as csv_string:
            csvwriter = csv.DictWriter(csv_string,
                                       fieldnames=self.columns.keys())
            if header:
                csvwriter.writeheader()
            csvwriter.writerow(self.columns)
            return csv_string.getvalue()


class Resistor(Component):
    table = "resistor"

    def __init__(self, resistance, tolerance, power, composition, package,
                 **kwargs):
        super().__init__(**kwargs)
        self.columns["resistance"] = resistance
        self.columns["tolerance"] = tolerance
        self.columns["power"] = power
        self.columns["composition"] = composition
        self.columns["package"] = package

    @staticmethod
    def process_resistance(param):
        """Return a processed resistance string, e.g. 10 or 1.0K.
        """
        resistance = re.search(r"\d+\.?\d*[kKmMG]?", param).group(0)
        return re.sub("k", "K", resistance)

    @staticmethod
    def process_tolerance(param):
        """Return a processed tolerance string, e.g. 5%, 1.0%, or -."""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "%"
        else:
            # e.g. jumpers have no meaningful tolerance
            return "-"

    @staticmethod
    def process_power(param):
        """Return a processed power string, e.g. 5W or 0.125W."""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "W"
        else:
            # e.g. jumpers have no meaningful power rating
            return "-"

    @staticmethod
    def process_composition(param):
        """Return a processed composition string, e.g. ThinFilm."""
        return re.sub(" ", "", param)

    @classmethod
    def from_digikey(cls, digikey_part):
        data = cls.get_digikey_common_data(digikey_part)

        for p in digikey_part.parameters:
            if p.parameter == "Resistance":
                data["resistance"] = cls.process_resistance(p.value)
            elif p.parameter == "Tolerance":
                data["tolerance"] = cls.process_tolerance(p.value)
            elif p.parameter == "Power (Watts)":
                data["power"] = cls.process_power(p.value)
            elif p.parameter == "Composition":
                raw_composition = p.value
                data["composition"] = cls.process_composition(raw_composition)
            elif p.parameter == "Supplier Device Package":
                data["package"] = p.value

        kicad_footprint_map = {
                "0201": "Resistor_SMD:R_0201_0603Metric",
                "0402": "Resistor_SMD:R_0402_1005Metric",
                "0603": "Resistor_SMD:R_0603_1608Metric",
                "0805": "Resistor_SMD:R_0805_2012Metric",
                "1206": "Resistor_SMD:R_1206_3216Metric",
                "1210": "Resistor_SMD:R_1210_3225Metric",
                }

        data["value"] = "${Resistance}"
        data["kicad_symbol"] = "Device:R"
        try:
            data["kicad_footprint"] = kicad_footprint_map[data["package"]]
        except KeyError as e:
            print_error(f"unknown footprint for package '{e}'")
            return None

        if data["resistance"] == "0":
            data["IPN"] = (
                    f"R_"
                    f"{data['resistance']}_"
                    f"Jumper_"
                    f"{data['package']}_"
                    f"{data['composition']}")
            data["description"] = (
                    f"0Ω Jumper "
                    f"{data['package']} "
                    f"{raw_composition}")
            data["keywords"] = "jumper"
        else:
            data["IPN"] = (
                    f"R_"
                    f"{data['resistance']}_"
                    f"{data['package']}_"
                    f"{data['tolerance']}_"
                    f"{data['power']}_"
                    f"{data['composition']}")
            data["description"] = (
                    f"{data['resistance']}Ω "
                    f"±{data['tolerance']} "
                    f"{data['power']} "
                    f"Resistor "
                    f"{data['package']} "
                    f"{raw_composition}")
            data["keywords"] = f"r res resistor {data['resistance']}"

        return cls(**data)


def create_component_from_digikey_pn(digikey_pn):
    """Factory to construct the appropriate component type object for a given
    digikey PN.

    Queries the digikey API to get part data, determines the component type,
    and then dispatches to the appropriate Component.from_digikey(part)
    constructor.

    Args:
        digikey_pn: string containing the digikey part number.

    Returns:
        A `Component` object constructed from the digikey part details.
    """
    part = digikey.product_details(digikey_pn)
    if not part:
        print_error(f"Could not get info for part {digikey_pn}")
        return None

    if part.limited_taxonomy.value == "Resistors":
        return Resistor.from_digikey(part)
    else:
        raise NotImplementedError("No component type to handle part type "
                                  f"'{part.limited_taxonomy.value}' for part "
                                  f"{digikey_pn}")


def create_component_from_dict(columns_and_values):
    """Factory to construct the appropriate component type object from a dict
    of column names to column values.

    All appropriate fields for each component type must be present. The type of
    component is determined from the value corresponding to the `IPN` key.

    Args:
        columns_and_values: dict containing all necessary key/value pairs for
            constructing the desired component.

    Returns:
        A `Component` object constructed from the given dict.
    """
    IPN = columns_and_values["IPN"]
    if IPN.startswith("R_"):
        return Resistor(**columns_and_values)
    else:
        raise NotImplementedError(f"No component type to handle part '{IPN}'")


def setup_digikey(config_data):
    """Set up environment variables and cache for digikey API calls.

    Args:
        config_data: dict of configuration data from config file.
    """
    DIGIKEY_DEFAULT_CACHE_DIR = os.path.expanduser(
            "~/.dblib_digikey_cache_dir")

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


def create_component_list_from_digikey_pns(digikey_pn_list):
    """Create a list of components from a list of digikey part numbers.

    Any part numbers that are invalid or otherwise cannot be used to create
    a component will be skipped.

    Args:
        digikey_pn_list: list of digikey part number strings.

    Returns:
        A list of Components corresponding to digikey part numbers.
    """

    try:
        setup_digikey(config_data)
    except KeyError as e:
        print_error(f"key {e.args[0]} not found in configuration file")
        return []

    components = []
    for pn in digikey_pn_list:
        comp = create_component_from_digikey_pn(pn)
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
    with open(args.csv, "r") as infile:
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
        sys.exit(f"Error: {db_path} already exists and cannot be "
                 "re-initialized.")
    con = sqlite3.connect(f"file:{db_path}", uri=True)
    con.close()


def add_component_to_db(db_path, comp, update=False):
    """Add the given component object to the database.

    The database is opened and closed within this function. The appropriate
    table is selected automatically, and created if it does not already exist.

    Args:
        db_path: path to database.
        comp: Component object to add to database.
        update: when True, an existing component in the database with the
            same IPN as the new component will be updated (REPLACE'd) by the
            new component. When False, the IPN of the new component will have a
            numeric suffix ('_1') added to avoid overwriting the existing
            component. If the modified IPN is still not unique, the suffix will
            be incremented (up to a maximum defined by IPN_DUPLICATE_LIMIT) in
            an attempt to create a unique IPN. After IPN_DUPLICATE_LIMIT
            unsuccessful attempts, the component will be skipped.
    """

    # TODO: move the connect/close outside of this function, and pass a
    # connection as an argument. This will let us handle the case where we
    # throw an exception in the unique-IPN loop without leaving a hanging
    # database connection.
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
        # con = sqlite3.connect(":memory:")
    except sqlite3.OperationalError:
        print_error(f"could not connect to database at path: {db_path}")
        return

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
                print_message(f"Updating existing component '{test_ipn}' in "
                              f"table '{comp.table}'")
            else:
                # we need to try to create a unique IPN
                for i in range(1, IPN_DUPLICATE_LIMIT):
                    test_ipn = f"{values['IPN']}_{i}"
                    if test_ipn not in ipns:
                        values["IPN"] = test_ipn
                        break
                if test_ipn != values["IPN"]:
                    # we didn't find a unique IPN
                    raise TooManyDuplicateIPNsInTableError(values["IPN"],
                                                           comp.table)

        # add part to table, whether this is:
        # 1) The base IPN (no duplicates)
        # 2) The base IPN (duplicate, but we're replacing an existing part)
        # 3) A modified IPN with a suffix to make it unique
        cur.execute(insert_string, values)

        print_message(f"Added component '{values['IPN']}' to table "
                      f"'{comp.table}'")

    con.close()


def add_components_from_list_to_db(db_path, components, update=False):
    """Add all components in a list to the database.

    Args:
        db_path: absolute path to database.
        components: list of components to add to database.
        update: if True, when duplicate components are encountered, update
            existing components instead of attempting to create a unique
            component.
    """
    for comp in components:
        try:
            add_component_to_db(db_path, comp, update)
        except TooManyDuplicateIPNsInTableError as e:
            print_error(f"too many parts with IPN '{e.IPN}' already in table "
                        f"'{e.table}'; skipped")


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
            description=("Add a part to the parts database, either manually "
                         "or by distributor lookup."))

    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print informational messages")

    parser.add_argument("--initializedb", action="store_true",
                        help="Initialize new, empty database")

    parser.add_argument("--update-existing", "-u", action="store_true",
                        help=("If specified part already exists in database, "
                              "update the existing component instead of "
                              "adding a new, unique part"))

    parser.add_argument("--no-db", action="store_true",
                        help=("Don't add part to database. This may be useful "
                              "in combination with another output format, "
                              "such as CSV."))

    parser.add_argument("--csv_output", action="store_true",
                        help=("Write part data to stdout, formatted as CSV. "
                              "Unless otherwise specified, parts are also "
                              "added to the database."))

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
            "--digikey", "-d", metavar="DIGIKEY_PN",
            help=("Digikey part number, or comma-separated list of part "
                  "numbers, for part(s) to add to database"))
    source_group.add_argument(
            "--mouser", "-m", metavar="MOUSER_PN",
            help=("Mouser part number, or comma-separated list of part "
                  "numbers, for part(s) to add to database"))
    source_group.add_argument(
            "--csv", "-p", metavar="CSVFILE",
            help=("CSV filename containing columns for all required part "
                  "parameters. Each row is a separate part"))

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    VERBOSE = args.verbose
    config_data = load_config()
    try:
        db_path = os.path.abspath(config_data["db"]["path"])
    except KeyError:
        sys.exit("Error: database path not found in config file")

    if args.initializedb:
        initialize_database(db_path)

    if not (args.digikey or args.mouser or args.csv):
        print_message("no parts to add")
        sys.exit()
    if args.digikey:
        digikey_pn_list = [pn.strip() for pn in args.digikey.split(",")]
        components = create_component_list_from_digikey_pns(digikey_pn_list)
    if args.mouser:
        raise NotImplementedError
    if args.csv:
        components = create_component_list_from_csv(args.csv)

    if not args.no_db:
        add_components_from_list_to_db(db_path, components,
                                       update=args.update_existing)

    if args.csv_output:
        print_components_from_list_as_csv(components)

