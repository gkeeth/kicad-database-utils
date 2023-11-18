from copy import deepcopy
import csv
import io
import os
import unittest
from unittest.mock import patch

from partdb import cli, db

from tests import digikey_mocks


class TestCLI(unittest.TestCase):
    db_path = "unittests.db"
    DPN_to_IPN = {
        "YAG2320CT-ND": "R_100_0603_1%_0.1W_ThinFilm",
        "311-0.0GRCT-ND": "R_0_Jumper_0603_ThickFilm",
    }
    DPNs = list(DPN_to_IPN.keys())

    def setUp(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def add_diode_to_db(self):
        cli.main(
            [
                "--database",
                self.db_path,
                "add",
                "--csv",
                "sample_parts_csv/BAT54WS-FDICT-ND.csv",
            ]
        )

    def check_table_and_IPN(self, table="resistor", IPNs=None, additional_checks={}):
        if IPNs is None:
            IPNs = [self.DPN_to_IPN[self.DPNs[0]]]

        con = db.connect_to_database(self.db_path)
        tables = db.get_table_names(con)
        self.assertEqual([f"{table}"], tables)

        expected_IPNs = [(IPN,) for IPN in IPNs]

        cur = con.cursor()
        res = cur.execute(f"SELECT IPN FROM {table}").fetchall()
        self.assertEqual(sorted(expected_IPNs), sorted(res))
        for col in additional_checks.keys():
            res = cur.execute(f"SELECT {col} from {table}").fetchall()
            self.assertEqual([(additional_checks[col],)], res)
        con.close()


class TestAdd(TestCLI):
    mock_resistor_updated = deepcopy(digikey_mocks.mock_resistor)
    mock_resistor_updated.primary_datasheet = "new_datasheet"

    @patch("digikey.product_details", return_value=digikey_mocks.mock_resistor)
    def test_add_from_digikey(self, resistor_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                self.DPNs[0],
            ]
        )
        self.check_table_and_IPN()

    @patch("digikey.product_details", return_value=digikey_mocks.mock_resistor)
    def test_add_increment(self, resistor_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                self.DPNs[0],
                self.DPNs[0],
                "--increment-duplicates",
            ]
        )
        self.check_table_and_IPN(
            IPNs=["R_100_0603_1%_0.1W_ThinFilm", "R_100_0603_1%_0.1W_ThinFilm_1"]
        )

    @patch(
        "digikey.product_details",
        side_effect=[digikey_mocks.mock_resistor, mock_resistor_updated],
    )
    def test_add_update(self, resistor_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                self.DPNs[0],
                self.DPNs[0],
                "--update-existing",
            ]
        )
        self.check_table_and_IPN(
            IPNs=["R_100_0603_1%_0.1W_ThinFilm"],
            additional_checks={"datasheet": "new_datasheet"},
        )

    def test_add_from_csv(self):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                f"sample_parts_csv/{self.DPNs[0]}.csv",
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
                f"sample_parts_csv/{self.DPNs[0]}.csv",
            ]
        )
        self.assertEqual(
            "Creating table 'resistor'\n"
            f"Adding component '{self.DPN_to_IPN[self.DPNs[0]]}' to table 'resistor'\n",
            stdout_mock.getvalue(),
        )

    def test_add_multiple(self):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                f"sample_parts_csv/{self.DPNs[0]}.csv",
                f"sample_parts_csv/{self.DPNs[1]}.csv",
            ]
        )
        self.check_table_and_IPN(IPNs=self.DPN_to_IPN.values())

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("digikey.product_details", return_value=digikey_mocks.mock_resistor)
    def test_add_dump_part_csv(self, resistor_mock, stdout_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                self.DPNs[0],
                "--dump-part-csv",
            ]
        )
        with open(f"sample_parts_csv/{self.DPNs[0]}.csv", "r") as f:
            expected = csv.DictReader(f)
            actual = csv.DictReader(stdout_mock.getvalue().split("\n"))
            for row_expected, row_actual in zip(expected, actual):
                self.assertEqual(row_expected, row_actual)

    @patch("builtins.print")
    @patch("digikey.product_details", return_value=digikey_mocks.mock_resistor)
    def test_add_dump_api_response(self, resistor_mock, print_mock):
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--digikey",
                self.DPNs[0],
                "--dump-api-response",
            ]
        )
        print_mock.assert_called_with(resistor_mock.return_value)


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
                f"sample_parts_csv/{self.DPNs[0]}.csv",
                f"sample_parts_csv/{self.DPNs[1]}.csv",
            ]
        )

    def test_remove_one(self):
        cli.main(
            [
                "--database",
                self.db_path,
                "rm",
                self.DPNs[1],
            ]
        )
        self.check_table_and_IPN()

    def test_remove_multiple(self):
        cli.main(
            [
                "--database",
                self.db_path,
                "rm",
                self.DPNs[1],
                self.DPN_to_IPN[self.DPNs[0]],  # remove 1 by DPN and 1 by IPN
            ]
        )
        self.check_table_and_IPN(IPNs=[])

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_remove_verbose(self, stdout_mock):
        cli.main(
            [
                "--verbose",
                "--database",
                self.db_path,
                "rm",
                self.DPNs[1],
            ]
        )
        self.assertEqual(
            f"Removing component '{self.DPN_to_IPN[self.DPNs[1]]}' "
            "from table 'resistor'\n",
            stdout_mock.getvalue(),
        )


class TestShow(TestCLI):
    def setUp(self):
        super().setUp()
        cli.main(
            [
                "--initialize-db",
                "--database",
                self.db_path,
                "add",
                "--csv",
                f"sample_parts_csv/{self.DPNs[0]}.csv",
                f"sample_parts_csv/{self.DPNs[1]}.csv",
            ]
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_table_names(self, stdout_mock):
        self.add_diode_to_db()
        cli.main(
            [
                "--database",
                self.db_path,
                "show",
                "--table-names-only",
                "--csv",
            ]
        )

        self.assertEqual("diode\nresistor\n", stdout_mock.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_csv_minimal(self, stdout_mock):
        self.add_diode_to_db()
        cli.main(
            [
                "--database",
                self.db_path,
                "show",
                "--minimal-columns",
                "--csv",
            ]
        )
        expected = (
            "distributor1,DPN1,distributor2,DPN2,kicad_symbol,kicad_footprint\r\n"
            "Digikey,BAT54WS-FDICT-ND,,,Device:D_Schottky,Diode_SMD:D_SOD-323\r\n"
            "Digikey,YAG2320CT-ND,,,Device:R,Resistor_SMD:R_0603_1608Metric\r\n"
            "Digikey,311-0.0GRCT-ND,,,Device:R,Resistor_SMD:R_0603_1608Metric\n"
        )

        self.assertEqual(
            expected,
            stdout_mock.getvalue(),
        )

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_csv_filter_tables(self, stdout_mock):
        self.add_diode_to_db()
        cli.main(
            [
                "--database",
                self.db_path,
                "show",
                "--minimal-columns",
                "--csv",
                "--tables",
                "resistor",
                "invalid_table",
            ]
        )
        expected = (
            "Error: skipping nonexistent tables: invalid_table\n"
            "distributor1,DPN1,distributor2,DPN2,kicad_symbol,kicad_footprint\r\n"
            "Digikey,YAG2320CT-ND,,,Device:R,Resistor_SMD:R_0603_1608Metric\r\n"
            "Digikey,311-0.0GRCT-ND,,,Device:R,Resistor_SMD:R_0603_1608Metric\n"
        )

        self.assertEqual(expected, stdout_mock.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_csv_full(self, stdout_mock):
        cli.main(
            [
                "--database",
                self.db_path,
                "show",
                "--all-columns",
                "--csv",
            ]
        )
        expected = (
            "DPN1,DPN2,IPN,MPN,composition,datasheet,description,"
            "distributor1,distributor2,exclude_from_board,exclude_from_bom,"
            "keywords,kicad_footprint,kicad_symbol,manufacturer,package,power,"
            "resistance,tolerance,value\r\n"
            "YAG2320CT-ND,,R_100_0603_1%_0.1W_ThinFilm,RT0603FRE07100RL,Thin Film,"
            "https://www.yageo.com/upload/media/product/productsearch/datasheet/"
            "rchip/PYu-RT_1-to-0.01_RoHS_L_15.pdf,"
            '"100Ω ±1%, 0.1W resistor, 0603, thin film",Digikey,,0,0,'
            "r res resistor 100,Resistor_SMD:R_0603_1608Metric,Device:R,YAGEO,"
            "0603,0.1W,100,1%,${Resistance}\r\n"
            "311-0.0GRCT-ND,,R_0_Jumper_0603_ThickFilm,RC0603JR-070RL,Thick Film,"
            "https://www.yageo.com/upload/media/product/productsearch/datasheet/"
            'rchip/PYu-RC_Group_51_RoHS_L_12.pdf,"0Ω jumper, 0603, thick film",'
            "Digikey,,0,0,jumper,Resistor_SMD:R_0603_1608Metric,Device:R,YAGEO,"
            "0603,-,0,-,${Resistance}\n"
        )

        self.assertEqual(expected, stdout_mock.getvalue())

    @patch("sys.stdout", new_callable=io.StringIO)
    def test_show_table_filter_columns(self, stdout_mock):
        self.add_diode_to_db()
        cli.main(
            [
                "--database",
                self.db_path,
                "show",
                "--columns",
                "IPN",
                "DPN1",
                "invalid_column",
            ]
        )
        expected = (
            "Error: skipping nonexistent columns: invalid_column\n"
            "IPN                               DPN1\n"
            "--------------------------------  ----------------\n"
            "D_DiodesIncorporated_BAT54WS-7-F  BAT54WS-FDICT-ND\n"
            "R_100_0603_1%_0.1W_ThinFilm       YAG2320CT-ND\n"
            "R_0_Jumper_0603_ThickFilm         311-0.0GRCT-ND\n"
        )

        self.assertEqual(expected, stdout_mock.getvalue())
