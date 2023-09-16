#! /usr/bin/env python

import sys
import os
import argparse
import sqlite3
import json
import requests

CONFIG_FILENAME = "~/.dblib_add_part_config.json"
AUTHORIZE_URL = "https://sandbox-api.digikey.com/v1/oauth2/authorize"
DB_FILENAME = "test.db"

common_cols = "IPN, display_name, package, datasheet, kicad_symbol, kicad_footprint, manufacturer, MPN, distributor1, DPN1, distributor2, DPN2, "

tables = {
        "resistor":             common_cols + "value, tolerance, power, material",
        "capacitor":            common_cols + "value, tolerance, voltage, dielectric",
        "inductor":             common_cols + "value, tolerance",
        "ferrite_bead":         common_cols + "impedance_at_freq, current, resistance",
        "connector":            common_cols + "series, circuit_configuration, gender, orientation",
        "led":                  common_cols + "color",
        "diode":                common_cols + "type, voltage",
        "transistor_bjt":       common_cols + "type",
        "transistor_mosfet":    common_cols + "type",
        "transistor_jfet":      common_cols + "type",
        "crystal":              common_cols + "frequency, load_capacitance",
        "potentiometer":        common_cols + "value, tolerance, power, material, orientation",
        "switch":               common_cols + "type, configuration, orientation, current",
        "relay":                common_cols + "configuration, coil_voltage, coil_current, switch_current",
        "opamp":                common_cols + "input_type, bandwidth",
        "logic":                common_cols + "function",
        "microcontroller":      common_cols + "pins, max_frequency",
        "voltage_regulator":    common_cols + "voltage, current",
        }


def initialize_database():
    """
    create a new database file and create blank tables according to the tables
    global variable.

    NOTE: does not close database connection
    """

    if os.path.isfile(DB_FILENAME):
        sys.exit(f"error: {DB_FILENAME} already exists and cannot be re-initialized.")
    # con = sqlite3.connect(f"file:{DB_FILENAME}", uri=True)
    con = sqlite3.connect(":memory:")

    try:
        with con:
            cur = con.cursor()
            for table in tables:
                cur.execute(f"CREATE TABLE {table}({tables[table]})")
            # print out tables to check that we did it right:
            res = cur.execute("SELECT name from sqlite_master")
            print(res.fetchall())
    except sqlite3.Error as err:
        print(err)


if __name__ == "__main__":
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

    args = parser.parse_args()

    if args.initializedb:
        initialize_database()
    else:
        # con = sqlite3.connect(f"file:{DB_FILENAME}?mode=rw", uri=True)
        con = sqlite3.connect(":memory:")
    # TODO: implement lookup by part number or manual entry
    if not (args.digikey or args.mouser or args.params):
        print("no parts to add")
        sys.exit()
    # TODO: error if we haven't selected a part type
    con.close()
