#! /usr/bin/env python

import sys
import os
import argparse
import sqlite3
import json
import digikey
import mouser

CONFIG_FILENAME = os.path.expanduser("~/.dblib_add_part_config.json")
# TODO: put cache dir and db filename into the configuration file
DIGIKEY_CACHE_DIR = os.path.expanduser("~/.dblib_digikey_cache_dir")
DB_FILENAME = "test.db"

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
        "resistor":             ", ".join(common_cols + ["value", "tolerance", "power", "material", "package"]),
        "capacitor":            ", ".join(common_cols + ["value", "tolerance", "voltage", "dielectric", "package"]),
        "inductor":             ", ".join(common_cols + ["value", "tolerance", "package"]),
        "ferrite_bead":         ", ".join(common_cols + ["impedance_at_freq", "current", "resistance", "package"]),
        "connector":            ", ".join(common_cols + ["series", "circuit_configuration", "gender", "orientation"]),
        "led":                  ", ".join(common_cols + ["color", "package"]),
        "diode":                ", ".join(common_cols + ["type", "voltage", "package"]),
        "transistor_bjt":       ", ".join(common_cols + ["type", "package"]),
        "transistor_mosfet":    ", ".join(common_cols + ["type", "package"]),
        "transistor_jfet":      ", ".join(common_cols + ["type", "package"]),
        "crystal":              ", ".join(common_cols + ["frequency", "load_capacitance", "package"]),
        "potentiometer":        ", ".join(common_cols + ["value", "tolerance", "power", "material", "orientation"]),
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


class PartInfoNotFoundException(Exception):
    pass


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
            "Resistance": "value",
            "Tolerance": "tolerance",
            "Power (Watts)": "power",
            "Composition": "material",
            "Supplier Device Package": "package",
            }

    data = get_digikey_common_info(part)
    for p in part.parameters:
        if p.parameter in digikey_resistor_map:
            data[digikey_resistor_map[p.parameter]] = p.value
    for column in digikey_resistor_map.values():
        if column not in data:
            raise PartInfoNotFoundException(
                    f"Could not find info for database column '{column}' in part data for {data['DPN1']}.")

    # TODO: now add to dictionary

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
        add_digikey_part_to_db(args.digikey)
    # TODO: error if we haven't selected a part type
