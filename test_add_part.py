#! /usr/bin/env python

import os
import sqlite3
import unittest

import add_part


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
        self.resistor = add_part.create_component_from_dict(self.base_dict)

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
            r = add_part.create_component_from_dict(self.base_dict)
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
            r = add_part.create_component_from_dict(self.base_dict)
            add_part.add_component_to_db(con, r)

        with self.assertRaises(
                add_part.TooManyDuplicateIPNsInTableError) as cm:
            r = add_part.create_component_from_dict(self.base_dict)
            add_part.add_component_to_db(con, r)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)
        con.close()


if __name__ == "__main__":
    unittest.main()
