import os
import unittest

from partdb import cli, db


class TestAdd(unittest.TestCase):
    db_path = "unittests.db"

    def setUp(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

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

        con = db.connect_to_database(self.db_path)
        tables = db.get_table_names(con)
        self.assertEqual(["resistor"], tables)

        cur = con.cursor()
        res = cur.execute("SELECT IPN FROM resistor").fetchall()
        self.assertEqual([("R_100_0603_1%_0.1W_ThinFilm",)], res)
        con.close()
