#! /usr/bin/env python

import os
import sqlite3
import unittest

from partdb import component  # for create_component_from_dict()
from partdb import db


class TestDatabaseFunctions(unittest.TestCase):
    db_path = "unittests.db"

    @staticmethod
    def create_dummy_component(IPN="R_test"):
        base_dict = {
            "IPN": IPN,
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
        return component.create_component_from_dict(base_dict)

    def setUp(self):
        self.backup_IPN_DUPLICATE_LIMIT = db.IPN_DUPLICATE_LIMIT
        db.initialize_database(self.db_path)
        self.con = sqlite3.connect(f"file:{self.db_path}?mode=rw", uri=True)
        self.cur = self.con.cursor()
        self.resistor = self.create_dummy_component()

    def tearDown(self):
        self.con.close()
        db.IPN_DUPLICATE_LIMIT = self.backup_IPN_DUPLICATE_LIMIT
        os.remove(self.db_path)

    def test_table_automatically_created(self):
        db.open_connection_and_add_component_to_db(self.db_path, self.resistor)

        res = self.cur.execute("SELECT name from sqlite_master").fetchall()

        self.assertIn(("resistor",), res)

    def test_unique_parts_in_table(self):
        db.open_connection_and_add_component_to_db(self.db_path, self.resistor)
        self.resistor.columns["IPN"] = "R_test2"
        db.open_connection_and_add_component_to_db(self.db_path, self.resistor)

        res = self.cur.execute("SELECT IPN from resistor").fetchall()

        self.assertIn(("R_test",), res)
        self.assertIn(("R_test2",), res)

    def test_update_existing_component(self):
        db.open_connection_and_add_component_to_db(self.db_path, self.resistor)
        self.resistor.columns["value"] = "val2"
        db.open_connection_and_add_component_to_db(
            self.db_path, self.resistor, update=True
        )

        res = self.cur.execute("SELECT value from resistor").fetchall()

        self.assertNotIn(("val",), res)
        self.assertIn(("val2",), res)

    def test_auto_increment_IPN(self):
        db.IPN_DUPLICATE_LIMIT = 3
        for n in range(db.IPN_DUPLICATE_LIMIT):
            r = self.create_dummy_component()
            r.columns["value"] = f"val{n}"
            db.add_component_to_db(self.con, r, increment=True)

        res = self.cur.execute("SELECT IPN, value from resistor").fetchall()

        self.assertIn(("R_test", "val0"), res)
        self.assertIn(("R_test_1", "val1"), res)
        self.assertIn(("R_test_2", "val2"), res)

    def test_too_many_duplicate_IPNs_increment(self):
        db.IPN_DUPLICATE_LIMIT = 3
        for n in range(db.IPN_DUPLICATE_LIMIT):
            r = self.create_dummy_component()
            r.columns["value"] = f"val{n}"
            db.add_component_to_db(self.con, r, increment=True)

        with self.assertRaises(db.TooManyDuplicateIPNsInTableError) as cm:
            r = self.create_dummy_component()
            db.add_component_to_db(self.con, r)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)

    def test_too_many_duplicate_IPNs(self):
        r = self.create_dummy_component()
        r.columns["value"] = "val"
        db.add_component_to_db(self.con, r, increment=False)

        with self.assertRaises(db.TooManyDuplicateIPNsInTableError) as cm:
            r = self.create_dummy_component()
            db.add_component_to_db(self.con, r, increment=False)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)


if __name__ == "__main__":
    unittest.main()
