#! /usr/bin/env python

from collections import defaultdict
import io
import os
import unittest
from unittest.mock import patch

from partdb import component  # for create_component_from_dict()
from partdb import db
from partdb.print_utils import set_verbose


class TestDatabaseFunctions(unittest.TestCase):
    db_path = "unittests.db"

    @staticmethod
    def create_dummy_component(IPN="R_test", **extra_fields):
        """Create a component based on a specified IPN, a default set of fields,
        and an optional additional set of fields.

        By default, the component will be a resistor, but this can be changed
        to an arbitrary component by providing an appropriate IPN and additional
        fields.

        Args:
            IPN: The IPN to use for the new component. Defaults to "R_test".
            **extra_fields: Additional fields to use when constructing the
                component. These can be new fields or override fields. These
                are necessary in order to create a component other than a
                resistor.

        Returns:
            A component created from the specified IPN, specified extra fields,
            and a base dictionary of fields.
        """

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
        base_dict.update(extra_fields)
        return component.create_component_from_dict(base_dict)

    @staticmethod
    def get_superset_keys(components):
        """Returns a string of the superset of column names for all components
        in the given iterable, sorted and comma-separated.
        """
        keys = set()
        for c in components:
            keys.update(c.columns.keys())
        return ",".join(sorted(keys))

    @staticmethod
    def get_csv_for_components(components, keys):
        """Return a CSV string for the given components, with `keys` as the
        column names.

        Args:
            components: an iterable of component objects to get values from.
            keys: a comma-separated string of column names.
        Returns:
            a CSV string containing a header line with column names and lines
            for each component.
        """
        rows = []
        for c in components:
            row = [str(defaultdict(str, c.columns)[k]) for k in keys.split(",")]
            rows.append(",".join(row))
        return "\r\n".join([keys] + rows)

    def setUp(self):
        self.backup_IPN_DUPLICATE_LIMIT = db.IPN_DUPLICATE_LIMIT
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        db.initialize_database(self.db_path)
        self.con = db.connect_to_database(self.db_path)
        self.cur = self.con.cursor()
        self.resistor = self.create_dummy_component()

    def tearDown(self):
        self.con.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        db.IPN_DUPLICATE_LIMIT = self.backup_IPN_DUPLICATE_LIMIT
        set_verbose(False)

    def test_add_table_automatically_created(self):
        db.add_component_to_db(self.con, self.resistor)

        res = self.cur.execute("SELECT name from sqlite_master").fetchall()

        self.assertIn(("resistor",), res)

    def test_add_unique_parts_in_table(self):
        db.add_component_to_db(self.con, self.resistor)
        self.resistor.columns["IPN"] = "R_test2"
        db.add_component_to_db(self.con, self.resistor)

        res = self.cur.execute("SELECT IPN from resistor").fetchall()

        self.assertIn(("R_test",), res)
        self.assertIn(("R_test2",), res)

    def test_add_update_existing_component(self):
        db.add_component_to_db(self.con, self.resistor)
        self.resistor.columns["value"] = "val2"
        db.add_component_to_db(self.con, self.resistor, update=True)

        res = self.cur.execute("SELECT value from resistor").fetchall()

        self.assertNotIn(("val",), res)
        self.assertIn(("val2",), res)

    def test_add_auto_increment_IPN(self):
        db.IPN_DUPLICATE_LIMIT = 3
        for n in range(db.IPN_DUPLICATE_LIMIT):
            r = self.create_dummy_component(value=f"val{n}")
            db.add_component_to_db(self.con, r, increment=True)

        res = self.cur.execute("SELECT IPN, value from resistor").fetchall()

        self.assertIn(("R_test", "val0"), res)
        self.assertIn(("R_test_1", "val1"), res)
        self.assertIn(("R_test_2", "val2"), res)

    def test_add_too_many_duplicate_IPNs_increment(self):
        db.IPN_DUPLICATE_LIMIT = 3
        for n in range(db.IPN_DUPLICATE_LIMIT):
            r = self.create_dummy_component(value=f"val{n}")
            db.add_component_to_db(self.con, r, increment=True)

        with self.assertRaises(db.TooManyDuplicateIPNsInTableError) as cm:
            r = self.create_dummy_component()
            db.add_component_to_db(self.con, r)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)

    def test_add_too_many_duplicate_IPNs(self):
        r = self.create_dummy_component()
        db.add_component_to_db(self.con, r, increment=False)

        with self.assertRaises(db.TooManyDuplicateIPNsInTableError) as cm:
            r = self.create_dummy_component()
            db.add_component_to_db(self.con, r, increment=False)
        e = cm.exception
        self.assertEqual("R_test", e.IPN)
        self.assertEqual("resistor", e.table)

    def test_dump_database_to_csv_full(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2")
        c1 = self.create_dummy_component(
            "C_1", capacitance="cap", voltage="volt", dielectric="X7R"
        )
        components = [c1, r1, r2]
        for comp in components:
            db.add_component_to_db(self.con, comp)

        expected_keys = self.get_superset_keys(components)
        expected = self.get_csv_for_components(components, expected_keys)

        dump = db.dump_database_to_csv(self.con, tables=None)

        self.assertEqual(expected, dump)

    def test_dump_database_to_csv_filter_tables(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2")
        c1 = self.create_dummy_component(
            "C_1", capacitance="cap", voltage="volt", dielectric="X7R"
        )
        components = [c1, r1, r2]
        for comp in components:
            db.add_component_to_db(self.con, comp)

        resistors = [r1, r2]
        expected_keys = self.get_superset_keys(resistors)
        expected = self.get_csv_for_components(resistors, expected_keys)

        dump = db.dump_database_to_csv(self.con, tables=["resistor"])

        self.assertEqual(expected, dump)

    def test_dump_database_to_csv_minimal(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2")
        c1 = self.create_dummy_component(
            "C_1", capacitance="cap", voltage="volt", dielectric="X7R"
        )
        components = [c1, r1, r2]
        for comp in components:
            db.add_component_to_db(self.con, comp)

        expected_keys = (
            "distributor1,DPN1,distributor2,DPN2,kicad_symbol,kicad_footprint"
        )
        expected = self.get_csv_for_components(components, expected_keys)

        dump = db.dump_database_to_csv(
            self.con, tables=None, columns=db.minimal_columns
        )

        self.assertEqual(expected, dump)

    def test_remove_by_IPN(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2", value="val2")
        for comp in [r1, r2]:
            db.add_component_to_db(self.con, comp)

        db.remove_component_from_db(self.con, "R_1")

        res = self.cur.execute("SELECT IPN from resistor").fetchall()
        self.assertNotIn(("R_1",), res)
        self.assertIn(("R_2",), res)

    def test_remove_by_DPN1(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2", value="val2", DPN1="dpn1a")
        for comp in [r1, r2]:
            db.add_component_to_db(self.con, comp)

        db.remove_component_from_db(self.con, "dpn1")

        res = self.cur.execute("SELECT IPN from resistor").fetchall()
        self.assertNotIn(("R_1",), res)
        self.assertIn(("R_2",), res)

    def test_remove_by_DPN2(self):
        r1 = self.create_dummy_component("R_1")  # default DPN2="dpn2"
        r2 = self.create_dummy_component("R_2", value="val2", DPN2="dpn2a")
        for comp in [r1, r2]:
            db.add_component_to_db(self.con, comp)

        db.remove_component_from_db(self.con, "dpn2")

        res = self.cur.execute("SELECT IPN from resistor").fetchall()
        self.assertNotIn(("R_1",), res)
        self.assertIn(("R_2",), res)

    def test_remove_skip_multiple_hits(self):
        r1 = self.create_dummy_component("R_1")
        r2 = self.create_dummy_component("R_2", value="val2")
        for comp in [r1, r2]:
            db.add_component_to_db(self.con, comp)

        db.remove_component_from_db(self.con, "dpn2")

        res = self.cur.execute("SELECT IPN from resistor").fetchall()
        self.assertIn(("R_1",), res)
        self.assertIn(("R_2",), res)

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_remove_no_hits(self, mock_stdout):
        db.add_component_to_db(self.con, self.resistor)
        set_verbose(True)
        db.remove_component_from_db(self.con, "R_nonexistent")
        res = self.cur.execute("SELECT IPN from resistor")
        self.assertIn(("R_test",), res)
        self.assertEqual(
            "No component matching 'R_nonexistent' found\n", mock_stdout.getvalue()
        )


if __name__ == "__main__":
    unittest.main()
