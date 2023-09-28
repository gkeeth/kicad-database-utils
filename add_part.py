#! /usr/bin/env python

import sys
import os
import re
from abc import ABC, abstractmethod
from collections import OrderedDict
import argparse
import sqlite3
import json
import digikey
import mouser

CONFIG_FILENAME = os.path.expanduser("~/.dblib_add_part_config.json")
# TODO: put cache dir and db filename into the configuration file
DIGIKEY_CACHE_DIR = os.path.expanduser("~/.dblib_digikey_cache_dir")
DB_FILENAME = "test.db"


class PartInfoNotFoundError(Exception):
    pass


class UnknownFootprintForPackageError(Exception):
    pass


class Component(ABC):
    def __init__(self, IPN, datasheet, description, keywords, value,
                 exclude_from_bom, exclude_from_board, kicad_symbol,
                 kicad_footprint, manufacturer, MPN, distributor1, DPN1,
                 distributor2, DPN2):
        # columns that all types of components need. Many of these map onto
        # KiCad builtin fields or properties.
        self.columns = OrderedDict()
        self.columns["IPN"] = IPN # unique ID for component
        self.columns["datasheet"] = datasheet
        self.columns["description"] = description
        self.columns["keywords"] = keywords
        self.columns["value"] = value
        self.columns["exclude_from_bom"] = exclude_from_bom
        self.columns["exclude_from_board"] = exclude_from_board
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
        """
        construct a component from a digikey part object.

        Needs to be implemented for each child class. TODO: @abstractmethod?
        """
        raise NotImplementedError

    @classmethod
    def get_digikey_common_data(cls, digikey_part):
        """return a dict of the common data from a digikey part object"""
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
        """return a sqlite string to create a table for the component type"""
        column_names = self.columns.keys()
        return f"CREATE TABLE {self.table}({column_names})"

    def get_insert_string(self):
        column_names = self.columns.keys()
        placeholders = ":" + ", :".join(column_names)
        return f"INSERT INTO {self.table} VALUES({placeholders})"


class Resistor(Component):
    table = "resistor"

    def __init__(self, resistance, tolerance, power, composition, package, **kwargs):
        super().__init__(**kwargs)
        self.columns["resistance"] = resistance
        self.columns["tolerance"] = tolerance
        self.columns["power"] = power
        self.columns["composition"] = composition
        self.columns["package"] = package

    @staticmethod
    def process_resistance(param):
        """return a processed resistance string in the form <resistance in ohms>"""
        resistance = re.search(r"\d+\.?\d*[kKmMG]?", param).group(0)
        return re.sub("k", "K", resistance)

    @staticmethod
    def process_tolerance(param):
        """return a processed tolerance string in the form <tolerance>%"""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "%"
        else:
            return "-"

    @staticmethod
    def process_power(param):
        """return a processed power string in the form <power>W"""
        match = re.search(r"\d+\.?\d*", param)
        if match:
            return match.group(0) + "W"
        else:
            return "-"

    @staticmethod
    def process_composition(param):
        """return a processed composition string, e.g. ThinFilm"""
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
                "0603": "Resistor_SMD:R_0603_1608Metric",
                "0805": "Resistor_SMD:R_0805_2012Metric",
                }

        data["value"] = "${Resistance}"
        data["kicad_symbol"] = "Device:R"
        data["kicad_footprint"] = kicad_footprint_map[data["package"]]
        data["exclude_from_bom"] = 0
        data["exclude_from_board"] = 0

        if data["resistance"] == "0":
            data["IPN"] = (f"R_{data['resistance']}_Jumper_{data['package']}_"
                           f"{data['composition']}")
            data["description"] = f"0Ω Jumper {data['package']} {raw_composition}"
            data["keywords"] = "jumper"
        else:
            data["IPN"] = (f"R_{data['resistance']}_{data['package']}_"
                           f"{data['tolerance']}_{data['power']}_"
                           f"{data['composition']}")
            data["description"] = (f"{data['resistance']}Ω ±{data['tolerance']} "
                                   f"{data['power']} Resistor {data['package']} "
                                   f"{raw_composition}")
            data["keywords"] = f"r res resistor {data['resistance']}"

        return cls(**data)


def create_component_from_digikey_pn(digikey_pn):
    """
    factory to construct the appropriate component type object for a given
    digikey PN.

    Queries the digikey API to get part data, determines the component type,
    and then dispatches to the appropriate Component.from_digikey(part)
    constructor.
    """
    part = digikey.product_details(digikey_pn)
    if not part:
        print(f"Could not get info for part {digikey_pn}")
        return None

    if part.limited_taxonomy.value == "Resistors":
        return Resistor.from_digikey(part)
    else:
        raise NotImplementedError(f"No component type to handle part {digikey_pn}")


common_cols = [
        "IPN",
        "display_name",
        "datasheet",
        "description",
        "keywords",
        "exclude_from_bom",
        "exclude_from_board",
        "kicad_symbol",
        "kicad_footprint",
        "manufacturer",
        "MPN",
        "distributor1",
        "DPN1",
        "distributor2",
        "DPN2",
        ]

tables = {
        "resistor":             ", ".join(common_cols + ["value", "resistance", "tolerance", "power", "composition", "package"]),
        "capacitor":            ", ".join(common_cols + ["value", "capacitance", "tolerance", "voltage", "dielectric", "package"]),
        "inductor":             ", ".join(common_cols + ["value", "inductance", "tolerance", "package"]),
        "ferrite_bead":         ", ".join(common_cols + ["impedance_at_freq", "current", "resistance", "package"]),
        "connector":            ", ".join(common_cols + ["series", "circuit_configuration", "gender", "orientation"]),
        "led":                  ", ".join(common_cols + ["color", "package"]),
        "diode":                ", ".join(common_cols + ["type", "voltage", "package"]),
        "transistor_bjt":       ", ".join(common_cols + ["type", "package"]),
        "transistor_mosfet":    ", ".join(common_cols + ["type", "package"]),
        "transistor_jfet":      ", ".join(common_cols + ["type", "package"]),
        "crystal":              ", ".join(common_cols + ["frequency", "load_capacitance", "package"]),
        "potentiometer":        ", ".join(common_cols + ["value", "tolerance", "power", "composition", "orientation"]),
        "switch":               ", ".join(common_cols + ["type", "configuration", "orientation", "current"]),
        "relay":                ", ".join(common_cols + ["configuration", "coil_voltage", "coil_current", "switch_current"]),
        "opamp":                ", ".join(common_cols + ["input_type", "bandwidth", "package"]),
        "logic":                ", ".join(common_cols + ["function", "package"]),
        "microcontroller":      ", ".join(common_cols + ["pins", "max_frequency", "package"]),
        "voltage_regulator":    ", ".join(common_cols + ["voltage", "current", "package"]),
        }


def initialize_database():
    """
    create a new database file and create blank tables according to the tables
    global variable.

    NOTE: does not close database connection
    """

    if os.path.isfile(DB_FILENAME):
        sys.exit(f"error: {DB_FILENAME} already exists and cannot be re-initialized.")
    con = sqlite3.connect(f"file:{DB_FILENAME}", uri=True)
    # con = sqlite3.connect(":memory:")

    try:
        with con:
            cur = con.cursor()
            for table in tables:
                cur.execute(f"CREATE TABLE {table}({tables[table]})")

            # print out tables to check that we did it right:
            res = cur.execute("SELECT name from sqlite_master")
            print(res.fetchall())

            if 0:
                # add some dummy data to resistor and capacitor tables
                cur.execute("""
                    INSERT INTO resistor VALUES
                        ("R001", "R_0603_10K_1%", "0603", "https://www.seielect.com/catalog/sei-rncp.pdf", "Device:R", "Resistor_SMD:R_0603_1608Metric", "Stackpole Electronics Inc", "RNCP0603FTD10K0", "Digikey", "RNCP0603FTD10K0CT-ND", "", "", "10k", "1%", "0.125", "Thin Film"),
                        ("R002", "R_0603_1K_1%", "0603", "https://www.seielect.com/catalog/sei-rncp.pdf", "Device:R", "Resistor_SMD:R_0603_1608Metric", "Stackpole Electronics Inc", "RNCP0603FTD1K00", "Digikey", "RNCP0603FTD1K00CT-ND", "", "", "1k", "1%", "0.125", "Thin Film")""")
                cur.execute("""
                    INSERT INTO capacitor VALUES
                        ("C001", "C_0603_100N_X7R_100V", "0603", "https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/609/CL10B104KB8NNNC_Spec.pdf", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "Samsung Electro-Mechanics", "CL10B104KB8NNNC", "Digikey", "1276-1000-1-ND", "", "", "100n", "+/-10%", "50V", "X7R"),
                        ("C002", "C_0603_10N_X7R_100V", "0603", "https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/609/CL10B104KB8NNNC_Spec.pdf", "Device:C", "Capacitor_SMD:C_0603_1608Metric", "Samsung Electro-Mechanics", "CL10B103KB8NNNC", "Digikey", "1276-1009-1-ND", "", "", "10n", "+/-10%", "50V", "X7R")""")

                # check
                res = cur.execute("SELECT display_name from resistor")
                print(res.fetchall())
                res = cur.execute("SELECT display_name from capacitor")
                print(res.fetchall())


    except sqlite3.Error as err:
        print(err)


def parse_args():
    """ set up CLI args and return the parsed arguments """
    parser = argparse.ArgumentParser(
            description="Add a part to the parts database, either manually or by distributor lookup.")
    parser.add_argument("--initializedb", action="store_true", help="Initialize database")
    parser.add_argument("--update-existing", "-u", action="store_true",
                        help="Update existing part in database instead of erroring if specified part already exists")

    #TODO: add arg for adding new tables (including columns) to existing database

    table_group = parser.add_mutually_exclusive_group()
    for t in tables:
        table_group.add_argument(f"--{t}", action="store_true",
                                 help=f"Add a new part to the {t} table")

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--digikey", "-d", metavar="DIGIKEY_PN",
                              help="Digikey part number for part to add to database")
    source_group.add_argument("--mouser", "-m", metavar="MOUSER_PN",
                              help="Mouser part number for part to add to database")
    source_group.add_argument("--params", "-p", metavar="PARAMLIST",
                              help="TODO: figure out how to specify these. csv?")

    return parser.parse_args()




def setup_digikey():
    with open(CONFIG_FILENAME, "r") as f:
        config_data = json.load(f)
    os.environ["DIGIKEY_CLIENT_ID"] = config_data["digikey"]["client_id"]
    os.environ["DIGIKEY_CLIENT_SECRET"] = config_data["digikey"]["client_secret"]
    os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"
    os.environ["DIGIKEY_STORAGE_PATH"] = DIGIKEY_CACHE_DIR
    if not os.path.isdir(DIGIKEY_CACHE_DIR):
        os.mkdir(DIGIKEY_CACHE_DIR)




digikey_capacitor_map = {
        "value": "",
        "tolerance": "Tolerance",
        "voltage": "Voltage - Rated",
        "dielectric": "",
        }

# TODO: add maps for categories other than resistors/caps


def get_digikey_common_info(part):
    common_data = {
            "datasheet":            part.primary_datasheet,
            "description":          part.detailed_description,
            "manufacturer":         part.manufacturer.value,
            "MPN":                  part.manufacturer_part_number,
            "distributor1":         "Digikey",
            "DPN1":                 part.digi_key_part_number,
            "distributor2":         "",
            "DPN2":                 "",
            }
    return common_data

def get_digikey_resistor_info(part):

    # map of digikey token names to database fields
    digikey_resistor_map = {
            "Resistance": "resistance",
            "Tolerance": "tolerance",
            "Power (Watts)": "power",
            "Composition": "composition",
            "Supplier Device Package": "package",
            }

    data = get_digikey_common_info(part)
    for p in part.parameters:
        if p.parameter in digikey_resistor_map:
            data[digikey_resistor_map[p.parameter]] = p.value

    # above we're iterating through what Digikey returned and checking if we're
    # interested, so now we need to check that we've found all the things that
    # we care about
    for column in digikey_resistor_map.values():
        if column not in data:
            raise PartInfoNotFoundError(
                    f"Could not find info for database column '{column}' in part data for {data['DPN1']}.")

    # TODO: post process data fields to be normalized:
    # - power = 0.1W
    # - tolerance = 1%
    # - resistance = 1k
    # - composition = thin film

    # TODO: construct custom description and IPN
    # TODO: decide how to make unique identifier
    footprint_map = {
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
        data["kicad_footprint"] = footprint_map[data["package"]]
    except KeyError as e:
        raise UnknownFootprintForPackageError(e)

    # display_name = f"R_{}"

    return data

def get_table_from_digikey_part(digikey_pn, part):
    """
    extract the part type from the digikey part metadata and convert it to a
    table name in our database.

    Returns the appropriate table name, or None if no appropriate table name
    was found.

    Prints a message if the appropriate table name wasn't found.
    """

    component_type_map = {
            "Chip Resistor - Surface Mount": "resistor",
            # TODO: add other resistor types
            "Ceramic Capacitors": "capacitor",
            # TODO: add other caps, like film and electrolytic
            "": "inductor",
            "": "ferrite_bead",
            "Rectangular Connectors - Headers, Male Pins - Headers, Male Pins": "connector",
            # TODO: add other types of connectors (including female)
            "LED Indication - Discrete": "led",
            "Diodes - Rectifiers - Single Diodes - Rectifiers - Single Diodes": "diode",
            "": "transistor_bjt",
            "": "transistor_mosfet",
            "": "transistor_jfet",
            "": "crystal",
            "Rotary Potentiometers, Rheostats": "potentiometer",
            "": "switch",
            "": "relay",
            "Linear - Amplifiers - Instrumentation, OP Amps, Buffer Amps - Amplifiers - Instrumentation, OP Amps, Buffer Amps": "opamp",
            "": "logic",
            "": "microcontroller",
            "": "voltage_regulator",
            }

    part_type = part.limited_taxonomy.children[0].value

    if part_type in component_type_map:
        return component_type_map[part_type]
    else:
        print(f"Unknown part type: '{part_type}' for part {digikey_pn}")
        return None


def add_digikey_part_to_db(digikey_pn):
    part = digikey.product_details(digikey_pn)
    if not part:
        print(f"Could not get info for part {digikey_pn}")
        return

    table = get_table_from_digikey_part(digikey_pn, part)
    if not table:
        return

    table_to_infofunc = {
        "resistor":             get_digikey_resistor_info,
        # "capacitor":
        # "inductor":
        # "ferrite_bead":
        # "connector":
        # "led":
        # "diode":
        # "transistor_bjt":
        # "transistor_mosfet":
        # "transistor_jfet":
        # "crystal":
        # "potentiometer":
        # "switch":
        # "relay":
        # "opamp":
        # "logic":
        # "microcontroller":
        # "voltage_regulator":
        }

    data = table_to_infofunc[table](part)
    insert_string = (f"INSERT INTO {table} VALUES("
                     f":{', :'.join(tables[table].split(', '))})")
    print(f"data: {data}")
    print(f"insert_string: {insert_string}")

    con = sqlite3.connect(f"file:{DB_FILENAME}?mode=rw", uri=True)
    # con = sqlite3.connect(":memory:")
    with con:
        cur = con.cursor()
        cur.execute(insert_string, data)

    con.close()


if __name__ == "__main__":
    args = parse_args()

    if args.initializedb:
        initialize_database()

    # TODO: implement lookup by part number or manual entry
    if not (args.digikey or args.mouser or args.params):
        print("no parts to add")
        sys.exit()
    if args.digikey:
        setup_digikey()
        create_component_from_digikey_pn(args.digikey)
    # TODO: error if we haven't selected a part type
