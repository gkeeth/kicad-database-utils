import os
import unittest
from unittest.mock import patch

from partdb import cli, db

from tests import digikey_mocks


class TestAdd(unittest.TestCase):
    db_path = "unittests.db"

    def setUp(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def check_table_and_IPN(self, table="resistor", IPN="R_100_0603_1%_0.1W_ThinFilm"):
        con = db.connect_to_database(self.db_path)
        tables = db.get_table_names(con)
        self.assertEqual([f"{table}"], tables)

        cur = con.cursor()
        res = cur.execute(f"SELECT IPN FROM {table}").fetchall()
        self.assertEqual([(IPN,)], res)
        con.close()

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
