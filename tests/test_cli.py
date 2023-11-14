import io
import os
import unittest
from unittest.mock import patch

from partdb import cli, db

from tests import digikey_mocks

"""
TODO tests
- verbose
- dump-database-csv-full
- dump-database-csv-minimal
- increment-duplicates, maybe
- update-existing, maybe
- dump-part-csv
- dump-api-response
"""


class TestCLI(unittest.TestCase):
    db_path = "unittests.db"

    def setUp(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def check_table_and_IPN(
        self, table="resistor", IPNs=["R_100_0603_1%_0.1W_ThinFilm"]
    ):
        con = db.connect_to_database(self.db_path)
        tables = db.get_table_names(con)
        self.assertEqual([f"{table}"], tables)

        expected_IPNs = [(IPN,) for IPN in IPNs]

        cur = con.cursor()
        res = cur.execute(f"SELECT IPN FROM {table}").fetchall()
        self.assertEqual(sorted(expected_IPNs), sorted(res))
        con.close()


class TestAdd(TestCLI):
    @patch("digikey.product_details", return_value=digikey_mocks.mock_resistor)
    def test_add_from_digikey(self, resistor_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                "YAG2320CT-ND",
            ]
        )
        self.check_table_and_IPN()

    def test_add_from_csv(self):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                "sample_parts_csv/YAG2320CT-ND.csv",
            ]
        )
        self.check_table_and_IPN()

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_add_verbose(self, stdout_mock):
        cli.main(
            [
                "--initialize-db",
                "--verbose",
                "--database",
                self.db_path,
                "add",
                "--csv",
                "sample_parts_csv/YAG2320CT-ND.csv",
            ]
        )
        self.assertEqual(
            "Creating table 'resistor'\n"
            "Adding component 'R_100_0603_1%_0.1W_ThinFilm' to table 'resistor'\n",
            stdout_mock.getvalue()
        )

    def test_add_multiple(self):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                "sample_parts_csv/YAG2320CT-ND.csv",
                "sample_parts_csv/311-0.0GRCT-ND.csv",
            ]
        )
        self.check_table_and_IPN(
            IPNs=["R_100_0603_1%_0.1W_ThinFilm", "R_0_Jumper_0603_ThickFilm"]
        )


class TestRm(TestCLI):
    def setUp(self):
        super().setUp()
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                "sample_parts_csv/YAG2320CT-ND.csv",
                "sample_parts_csv/311-0.0GRCT-ND.csv",
            ]
        )

    def test_remove_one(self):
        cli.main(
            [
                "--database",
                self.db_path,
                "rm",
                "311-0.0GRCT-ND",
            ]
        )
        self.check_table_and_IPN()

    def test_remove_multiple(self):
        cli.main(
            [
                "--database",
                self.db_path,
                "rm",
                "311-0.0GRCT-ND",
                "R_100_0603_1%_0.1W_ThinFilm",
            ]
        )
        self.check_table_and_IPN(IPNs=[])
