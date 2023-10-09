#! /usr/bin/env python

import unittest
from unittest.mock import patch, MagicMock
import os
import sqlite3
import csv

import add_part
from add_part import Resistor, Capacitor


class TestCreateFromDigikey(unittest.TestCase):
    @staticmethod
    def expected_from_csv(csvpath):
        with open(csvpath, "r") as infile:
            reader = csv.DictReader(infile)
            return add_part.create_component_from_dict(next(reader))

    def disabled_test_resistor_from_digikey_pn_nomock(self):
        add_part.setup_digikey(add_part.load_config())
        actual = add_part.create_component_from_digikey_pn("YAG2320CT-ND")
        expected = self.expected_from_csv("sample_parts_csv/YAG2320CT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("digikey.product_details")
    def test_resistor_from_digikey_pn(self, mock_product_details):
        mock_part = mock_product_details.return_value
        mock_part.limited_taxonomy.value = "Resistors"
        mock_part.primary_datasheet = (
                "https://www.yageo.com/upload/media/product/productsearch/"
                "datasheet/rchip/PYu-RT_1-to-0.01_RoHS_L_13.pdf")
        mock_part.manufacturer.value = "YAGEO"
        mock_part.manufacturer_part_number = "RT0603FRE07100RL"
        mock_part.digi_key_part_number = "YAG2320CT-ND"

        mock_part.parameters = [
                MagicMock(parameter="Resistance", value="100Ω"),
                MagicMock(parameter="Tolerance", value="±1%"),
                MagicMock(parameter="Power (Watts)", value="0.1W"),
                MagicMock(parameter="Composition", value="Thin Film"),
                MagicMock(parameter="Supplier Device Package", value="0603"),
                ]

        actual = add_part.create_component_from_digikey_pn("YAG2320CT-ND")
        expected = self.expected_from_csv("sample_parts_csv/YAG2320CT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def disabled_test_ceramic_capacitor_from_digikey_pn_nomock(self):
        add_part.setup_digikey(add_part.load_config())
        actual = add_part.create_component_from_digikey_pn("1276-1123-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/1276-1123-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("digikey.product_details")
    def test_ceramic_capacitor_from_digikey_pn(self, mock_product_details):
        mock_part = mock_product_details.return_value
        mock_part.limited_taxonomy.value = "Capacitors"
        mock_part.primary_datasheet = (
                "https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/"
                "1068/CL21B334KBFNNNE_Spec.pdf")
        mock_part.manufacturer.value = "Samsung Electro-Mechanics"
        mock_part.manufacturer_part_number = "CL21B334KBFNNNE"
        mock_part.digi_key_part_number = "1276-1123-1-ND"

        mock_part.family.value = "Ceramic Capacitors"

        mock_part.parameters = [
                MagicMock(parameter="Capacitance", value="0.33 µF"),
                MagicMock(parameter="Tolerance", value="±10%"),
                MagicMock(parameter="Voltage - Rated", value="50V"),
                MagicMock(parameter="Temperature Coefficient", value="X7R"),
                MagicMock(
                    parameter="Package / Case", value="0805 (2012 Metric)"),
                ]

        actual = add_part.create_component_from_digikey_pn("1276-1123-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/1276-1123-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def disabled_test_electrolytic_capacitor_from_digikey_pn_nomock(self):
        add_part.setup_digikey(add_part.load_config())
        actual = add_part.create_component_from_digikey_pn("493-13313-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/493-13313-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("digikey.product_details")
    def test_electrolytic_capacitor_from_digikey_pn(self, mock_product_details):
        mock_part = mock_product_details.return_value
        mock_part.limited_taxonomy.value = "Capacitors"
        mock_part.primary_datasheet = (
                "https://www.nichicon.co.jp/english/series_items/"
                "catalog_pdf/e-ucy.pdf")
        mock_part.manufacturer.value = "Nichicon"
        mock_part.manufacturer_part_number = "UCY2G100MPD1TD"
        mock_part.digi_key_part_number = "493-13313-1-ND"

        mock_part.family.value = "Aluminum Electrolytic Capacitors"

        mock_part.parameters = [
                MagicMock(parameter="Capacitance", value="10 µF"),
                MagicMock(parameter="Tolerance", value="±20%"),
                MagicMock(parameter="Voltage - Rated", value="400V"),
                MagicMock(parameter="Package / Case", value="Radial, Can"),
                MagicMock(parameter="Polarization", value="Polar"),
                MagicMock(parameter="Size / Dimension",
                          value='0.394" Dia (10.00mm)'),
                MagicMock(parameter="Height - Seated (Max)",
                          value='0.689" (17.50mm)'),
                MagicMock(parameter="Lead Spacing", value='0.197" (5.00mm)'),
                ]

        actual = add_part.create_component_from_digikey_pn("493-13313-1-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/493-13313-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def disabled_test_nonpolarized_electrolytic_capacitor_from_digikey_pn_nomock(self):
        add_part.setup_digikey(add_part.load_config())
        actual = add_part.create_component_from_digikey_pn(
                "10-ECE-A1HN100UBCT-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/10-ECE-A1HN100UBCT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("digikey.product_details")
    def test_unpolarized_electrolytic_capacitor_from_digikey_pn(
            self, mock_product_details):
        mock_part = mock_product_details.return_value
        mock_part.limited_taxonomy.value = "Capacitors"
        mock_part.primary_datasheet = (
           "https://industrial.panasonic.com/cdbs/www-data/pdf/"
           "RDF0000/ABA0000C1053.pdf")
        mock_part.manufacturer.value = "Panasonic Electronic Components"
        mock_part.manufacturer_part_number = "ECE-A1HN100UB"
        mock_part.digi_key_part_number = "10-ECE-A1HN100UBCT-ND"

        mock_part.family.value = "Aluminum Electrolytic Capacitors"

        mock_part.parameters = [
                MagicMock(parameter="Capacitance", value="10 µF"),
                MagicMock(parameter="Tolerance", value="±20%"),
                MagicMock(parameter="Voltage - Rated", value="50V"),
                MagicMock(parameter="Package / Case", value="Radial, Can"),
                MagicMock(parameter="Polarization", value="Bi-Polar"),
                MagicMock(parameter="Size / Dimension",
                          value='0.248" Dia (6.30mm)'),
                MagicMock(parameter="Height - Seated (Max)",
                          value='0.480" (12.20mm)'),
                MagicMock(parameter="Lead Spacing", value='0.197" (5.00mm)'),
                ]

        actual = add_part.create_component_from_digikey_pn(
                "10-ECE-A1HN100UBCT-ND")
        expected = self.expected_from_csv(
                "sample_parts_csv/10-ECE-A1HN100UBCT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())


class TestComponentOutputs(unittest.TestCase):
    def setUp(self):
        # we use Resistor here as the simplest (?) subclass of Component,
        # but we're really testing the baseclass export methods
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

    def test_to_csv(self):
        header = ("IPN,datasheet,description,keywords,value,exclude_from_bom,"
                  "exclude_from_board,kicad_symbol,kicad_footprint,"
                  "manufacturer,MPN,distributor1,DPN1,distributor2,DPN2,"
                  "resistance,tolerance,power,composition,package\r\n")
        values = ("R_test,ds,desc,kw,val,0,0,sym,fp,mfg,mpn,dist1,dpn1,dist2,"
                  "dpn2,10k,1%,0.125W,ThinFilm,0603\r\n")
        self.assertEqual(header + values, self.resistor.to_csv())
        self.assertEqual(values, self.resistor.to_csv(header=False))

    def test_to_sql(self):
        columns = (":IPN, :datasheet, :description, :keywords, :value, "
                   ":exclude_from_bom, :exclude_from_board, :kicad_symbol, "
                   ":kicad_footprint, :manufacturer, :MPN, :distributor1, "
                   ":DPN1, :distributor2, :DPN2, :resistance, :tolerance, "
                   ":power, :composition, :package)")
        sql_update_expected = ("INSERT OR REPLACE INTO resistor VALUES("
                               + columns)
        sql_noupdate_expected = "INSERT INTO resistor VALUES(" + columns

        sql, vals = self.resistor.to_sql()
        self.assertEqual(sql_noupdate_expected, sql)
        self.assertEqual(self.base_dict, vals)

        sql, vals = self.resistor.to_sql(update=True)
        self.assertEqual(sql_update_expected, sql)
        self.assertEqual(self.base_dict, vals)

    def test_get_create_table_string(self):
        sql_expected = ("CREATE TABLE IF NOT EXISTS resistor("
                        "IPN PRIMARY KEY, datasheet, description, keywords, "
                        "value, exclude_from_bom, exclude_from_board, "
                        "kicad_symbol, kicad_footprint, manufacturer, MPN, "
                        "distributor1, DPN1, distributor2, DPN2, resistance, "
                        "tolerance, power, composition, package)")
        self.assertEqual(sql_expected, self.resistor.get_create_table_string())


class TestParameterUtils(unittest.TestCase):
    def test_process_resistance_no_suffix(self):
        self.assertEqual("1", Resistor.process_resistance("1"))
        self.assertEqual("10", Resistor.process_resistance("10"))
        self.assertEqual("1.0", Resistor.process_resistance("1.0"))
        self.assertEqual("1", Resistor.process_resistance("1 Ohm"))
        self.assertEqual("1", Resistor.process_resistance("1Ohm"))
        self.assertEqual("1", Resistor.process_resistance("1R"))
        self.assertEqual("1K", Resistor.process_resistance("1k"))
        self.assertEqual("1K", Resistor.process_resistance("1K"))
        self.assertEqual("1K", Resistor.process_resistance("1k Ohm"))
        self.assertEqual("1K", Resistor.process_resistance("1kOhm"))
        self.assertEqual("10K", Resistor.process_resistance("10kOhm"))
        self.assertEqual("1.00K", Resistor.process_resistance("1.00kOhm"))
        self.assertEqual("1m", Resistor.process_resistance("1m"))
        self.assertEqual("1M", Resistor.process_resistance("1M"))
        self.assertEqual("1G", Resistor.process_resistance("1G"))

    def test_process_tolerance(self):
        self.assertEqual("1%", Resistor.process_tolerance("1"))
        self.assertEqual("1%", Resistor.process_tolerance("1%"))
        self.assertEqual("10%", Capacitor.process_tolerance("10%"))
        self.assertEqual("1.00%", Resistor.process_tolerance("1.00%"))
        self.assertEqual("1%", Resistor.process_tolerance("±1%"))
        self.assertEqual("-", Resistor.process_tolerance("something weird"))

    def test_process_power(self):
        self.assertEqual("1W", Resistor.process_power("1"))
        self.assertEqual("1W", Resistor.process_power("1W"))
        self.assertEqual("10W", Resistor.process_power("10"))
        self.assertEqual("1.00W", Resistor.process_power("1.00"))
        self.assertEqual("-", Resistor.process_power("something weird"))

    def test_process_composition(self):
        self.assertEqual("ThinFilm", Resistor.process_composition("ThinFilm"))
        self.assertEqual("ThinFilm", Resistor.process_composition("Thin Film"))

    def test_process_capacitance(self):
        self.assertEqual("1nF", Capacitor.process_capacitance("1nF"))
        self.assertEqual("1nF", Capacitor.process_capacitance("1n"))
        self.assertEqual("1nF", Capacitor.process_capacitance("1 nF"))
        self.assertEqual("4.7nF", Capacitor.process_capacitance("4.7nF"))
        self.assertEqual("1fF", Capacitor.process_capacitance("1fF"))
        self.assertEqual("1fF", Capacitor.process_capacitance("1f"))
        self.assertEqual("1pF", Capacitor.process_capacitance("1pF"))
        self.assertEqual("1pF", Capacitor.process_capacitance("1PF"))
        self.assertEqual("1nF", Capacitor.process_capacitance("1NF"))
        self.assertEqual("1μF", Capacitor.process_capacitance("1uF"))
        self.assertEqual("1μF", Capacitor.process_capacitance("1UF"))
        self.assertEqual("1μF", Capacitor.process_capacitance("1μF"))
        self.assertEqual("1μF", Capacitor.process_capacitance("1µF"))
        self.assertEqual("1mF", Capacitor.process_capacitance("1mF"))
        self.assertEqual("1mF", Capacitor.process_capacitance("1MF"))
        self.assertEqual("1nF", Capacitor.process_capacitance("1000pF"))
        self.assertEqual("1.5μF", Capacitor.process_capacitance("1500nF"))
        self.assertEqual("999nF", Capacitor.process_capacitance("999nF"))
        self.assertEqual("999nF", Capacitor.process_capacitance("0.999uF"))
        self.assertEqual("0.1fF", Capacitor.process_capacitance("0.1fF"))
        self.assertEqual("1000mF", Capacitor.process_capacitance("1000mF"))
        self.assertEqual(
                "1000000mF", Capacitor.process_capacitance("1000000mF"))

    def test_process_voltage(self):
        self.assertEqual("5V", Capacitor.process_voltage("5V"))
        self.assertEqual("50V", Capacitor.process_voltage("50V"))
        self.assertEqual("50V", Capacitor.process_voltage("50 V"))
        self.assertEqual("50.0V", Capacitor.process_voltage("50.0 V"))

    def test_process_polarization(self):
        self.assertEqual(
                "Unpolarized", Capacitor.process_polarization("Bi-Polar"))
        self.assertEqual(
                "Polarized", Capacitor.process_polarization("Polar"))
        with self.assertRaisesRegex(ValueError,
                                    "Unknown capacitor polarization 'test'"):
            Capacitor.process_polarization("test")

    def test_process_package(self):
        self.assertEqual(
                "0805", Capacitor.process_package("0805 (2012 Metric)"))
        self.assertEqual(
                "Radial, Can", Capacitor.process_package("Radial, Can"))

    def test_process_dimension(self):
        self.assertEqual(
                "5.00mm", Capacitor.process_dimension("12.7in (5.00mm)"))
        self.assertEqual(
                "10.0mm", Capacitor.process_dimension("25.4in (10.00 mm)"))
        self.assertEqual(
                "5.00mm", Capacitor.process_dimension("5 mm"))


class TestComponentFromDict(unittest.TestCase):
    def setUp(self):
        self.base_dict = {
                "IPN": "dummy",
                "datasheet": "ds",
                "description": "desc",
                "keywords": "kw",
                "value": "val",
                "kicad_symbol": "sym",
                "kicad_footprint": "fp",
                "manufacturer": "mfg",
                "MPN": "mpn",
                "distributor1": "dist1",
                "DPN1": "dpn1",
                "distributor2": "dist2",
                "DPN2": "dpn2",
                }

    def _setup_resistor(self):
        self.base_dict["IPN"] = "R_test"
        self.base_dict["resistance"] = "10k"
        self.base_dict["tolerance"] = "1%"
        self.base_dict["power"] = "0.125W"
        self.base_dict["composition"] = "ThinFilm"
        self.base_dict["package"] = "0603"

    def test_unknown_not_detected(self):
        self.base_dict["IPN"] = "1"  # "1" is an unused IPN prefix
        with self.assertRaisesRegex(NotImplementedError,
                                    "No component type to handle part '1'"):
            add_part.create_component_from_dict(self.base_dict)

    def test_resistor_detected_from_IPN(self):
        self._setup_resistor()
        resistor = add_part.create_component_from_dict(self.base_dict)
        self.assertEqual("resistor", resistor.table)

    def test_resistor_values_correct(self):
        self._setup_resistor()
        resistor = add_part.create_component_from_dict(self.base_dict)
        for k in self.base_dict.keys():
            self.assertEqual(self.base_dict[k], resistor.columns[k])


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
