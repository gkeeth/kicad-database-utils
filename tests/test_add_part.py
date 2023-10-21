#! /usr/bin/env python

import csv
import os
import sqlite3
import unittest
from unittest.mock import patch

from partdb import component  # for create_component_from_dict()
from partdb import add_part


@unittest.skip("external API call")
class TestCreateFromDigikeyAPI(unittest.TestCase):
    @staticmethod
    def expected_from_csv(csvpath):
        with open(csvpath, "r") as infile:
            reader = csv.DictReader(infile)
            return component.create_component_from_dict(next(reader))

    def setUp(self):
        add_part.setup_digikey(add_part.load_config())

    def test_resistor_from_digikey_pn(self):
        actual = add_part.create_component_from_digikey_pn("YAG2320CT-ND")
        expected = self.expected_from_csv("sample_parts_csv/YAG2320CT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def test_ceramic_capacitor_from_digikey_pn(self):
        actual = add_part.create_component_from_digikey_pn("1276-1123-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/1276-1123-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Capacitor_THT:CP_Radial_D10.0mm_H17.5mm_P5.00mm")
    def test_electrolytic_capacitor_from_digikey_pn(self, mock_input):
        actual = add_part.create_component_from_digikey_pn("493-13313-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/493-13313-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Capacitor_THT:C_Radial_D6.30mm_H12.2mm_P5.00mm")
    def test_nonpolarized_electrolytic_capacitor_from_digikey_pn(
            self, mock_input):
        actual = add_part.create_component_from_digikey_pn(
                "10-ECE-A1HN100UBCT-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/10-ECE-A1HN100UBCT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Amplifier_Operational:LM4562")
    def test_opamp_from_digikey_pn(self, mock_input):
        actual = add_part.create_component_from_digikey_pn("296-35279-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/296-35279-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())


class TestDatabaseFunctions(unittest.TestCase):
    db_path = "unittests.db"

    def setUp(self):
        self.backup_IPN_DUPLICATE_LIMIT = add_part.IPN_DUPLICATE_LIMIT
        self.base_dict = {
                "IPN": "R_test",
                "datasheet": "ds",
                "description": "desc",
                "keywords": "kw",
                "value": "val",
                "exclude_from_bom": 0,
                "exclude_from_board": 0,
                "kicad_symbol": "sym",
                "kicad_footprint": "fp",
                "manufacturer": "mfg",
                "MPN": "mpn",
                "distributor1": "dist1",
                "DPN1": "dpn1",
                "distributor2": "dist2",
                "DPN2": "dpn2",
                "resistance": "10k",
                "tolerance": "1%",
                "power": "0.125W",
                "composition": "ThinFilm",
                "package": "0603",
                }
        self.resistor = component.create_component_from_dict(self.base_dict)

        add_part.initialize_database(self.db_path)

    def tearDown(self):
        add_part.IPN_DUPLICATE_LIMIT = self.backup_IPN_DUPLICATE_LIMIT
        os.remove(self.db_path)

    def test_table_automatically_created(self):
        add_part.open_connection_and_add_component_to_db(
                self.db_path, self.resistor)

        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cur = con.cursor()
        res = cur.execute("SELECT name from sqlite_master").fetchall()

        self.assertIn(("resistor",), res)

    def test_unique_parts_in_table(self):
        add_part.open_connection_and_add_component_to_db(
                self.db_path, self.resistor)
        self.resistor.columns["IPN"] = "R_test2"
        add_part.open_connection_and_add_component_to_db(
                self.db_path, self.resistor)

        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cur = con.cursor()
        res = cur.execute("SELECT IPN from resistor").fetchall()

        self.assertIn(("R_test",), res)
        self.assertIn(("R_test2",), res)

    def test_update_existing_component(self):
        add_part.open_connection_and_add_component_to_db(
                self.db_path, self.resistor)
        self.resistor.columns["value"] = "val2"
        add_part.open_connection_and_add_component_to_db(
                self.db_path, self.resistor, update=True)

        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        cur = con.cursor()
        res = cur.execute("SELECT value from resistor").fetchall()

        self.assertNotIn(("val",), res)
        self.assertIn(("val2",), res)

    def test_auto_increment_IPN(self):
        add_part.IPN_DUPLICATE_LIMIT = 3
        con = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        for n in range(add_part.IPN_DUPLICATE_LIMIT):
            self.base_dict["value"] = f"val{n}"
            r = component.create_component_from_dict(self.base_dict)
            add_part.add_component_to_db(con, r)

        cur = con.cursor()
        res = cur.execute("SELECT IPN, value from resistor").fetchall()

        self.assertIn(("R_test", "val0"), res)
        self.assertIn(("R_test_1", "val1"), res)
        self.assertIn(("R_test_2", "val2"), res)

    def test_too_many_duplicate_IPNs(self):
        add_part.IPN_DUPLICATE_LIMIT = 3
        con = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        for n in range(add_part.IPN_DUPLICATE_LIMIT):
            self.base_dict["value"] = f"val{n}"
            r = component.create_component_from_dict(self.base_dict)
            add_part.add_component_to_db(con, r)

        with self.assertRaises(
                add_part.TooManyDuplicateIPNsInTableError) as cm:
            r = component.create_component_from_dict(self.base_dict)
            add_part.add_component_to_db(con, r)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)
        con.close()


if __name__ == "__main__":
    unittest.main()
