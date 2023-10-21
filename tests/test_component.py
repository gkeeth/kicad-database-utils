#! /usr/bin/env python

import csv
import unittest
from unittest.mock import patch, MagicMock

# from partdb import component
from partdb import component
from partdb.component import Component, Resistor, Capacitor, OpAmp


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
        self.resistor = component.create_component_from_dict(self.base_dict)

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
    def test_process_resistance(self):
        testcases = [
                ("1", "1"),
                ("10", "10"),
                ("1.0", "1.0"),
                ("1", "1 Ohm"),
                ("1", "1Ohm"),
                ("1", "1R"),
                ("1K", "1k"),
                ("1K", "1K"),
                ("1K", "1k Ohm"),
                ("1K", "1kOhm"),
                ("10K", "10kOhm"),
                ("1.00K", "1.00kOhm"),
                ("1m", "1m"),
                ("1M", "1M"),
                ("1G", "1G"),
                ]
        for expected, r in testcases:
            with self.subTest(Resistance=r):
                self.assertEqual(expected, Resistor.process_resistance(r))

    def test_process_tolerance(self):
        testcases = [
                ("1%", "1"),
                ("1%", "1%"),
                ("10%", "10%"),
                ("1.00%", "1.00%"),
                ("1%", "±1%"),
                ("-", "something weird"),
                ]
        for expected, tol in testcases:
            with self.subTest(Tolerance=tol):
                self.assertEqual(expected, Component.process_tolerance(tol))

    def test_process_power(self):
        testcases = [
                ("1W", "1"),
                ("1W", "1W"),
                ("10W", "10"),
                ("1.00W", "1.00"),
                ("-", "something weird"),
                ]
        for expected, power in testcases:
            with self.subTest(Power=power):
                self.assertEqual(expected, Resistor.process_power(power))

    def test_process_composition(self):
        testcases = [
                ("ThinFilm", "ThinFilm"),
                ("ThinFilm", "Thin Film")
                ]
        for expected, comp in testcases:
            with self.subTest(Composition=comp):
                self.assertEqual(expected, Resistor.process_composition(comp))

    def test_process_capacitance(self):
        testcases = [
                ("1nF", "1nF"),
                ("1nF", "1n"),
                ("1nF", "1 nF"),
                ("4.7nF", "4.7nF"),
                ("1fF", "1fF"),
                ("1fF", "1f"),
                ("1pF", "1pF"),
                ("1pF", "1PF"),
                ("1nF", "1NF"),
                ("1μF", "1uF"),
                ("1μF", "1UF"),
                ("1μF", "1μF"),
                ("1μF", "1µF"),
                ("1mF", "1mF"),
                ("1mF", "1MF"),
                ("1nF", "1000pF"),
                ("1.5μF", "1500nF"),
                ("999nF", "999nF"),
                ("999nF", "0.999uF"),
                ("0.1fF", "0.1fF"),
                ("1000mF", "1000mF"),
                ("1000000mF", "1000000mF"),
                ]
        for expected, cap in testcases:
            with self.subTest(Capacitance=cap):
                self.assertEqual(expected, Capacitor.process_capacitance(cap))

    def test_process_voltage(self):
        testcases = [
                ("5V", "5V"),
                ("50V", "50V"),
                ("50V", "50 V"),
                ("50.0V", "50.0 V"),
                ]
        for expected, v in testcases:
            with self.subTest(Voltage=v):
                self.assertEqual(expected, Capacitor.process_voltage(v))

    def test_process_polarization(self):
        testcases = [
                ("Unpolarized", "Bi-Polar"),
                ("Polarized", "Polar"),
                ]
        for expected, pol in testcases:
            with self.subTest(Polarization=pol):
                self.assertEqual(expected, Capacitor.process_polarization(pol))

        with self.subTest(Polarization="test"):
            with self.assertRaisesRegex(
                    ValueError, "Unknown capacitor polarization 'test'"):
                Capacitor.process_polarization("test")

    def test_process_package(self):
        testcases = [
                ("0805", "0805 (2012 Metric)"),
                ("Radial, Can", "Radial, Can"),
                ]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(expected, Capacitor.process_package(package))

    def test_process_dimension(self):
        testcases = [
                ("5.00mm", "12.7in (5.00mm)"),
                ("10.0mm", "25.4in (10.00 mm)"),
                ("5.00mm", "5 mm"),
                ]
        for expected, dim in testcases:
            with self.subTest(Dimension=dim):
                self.assertEqual(expected, Capacitor.process_dimension(dim))


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
            component.create_component_from_dict(self.base_dict)

    def test_resistor_detected_from_IPN(self):
        self._setup_resistor()
        resistor = component.create_component_from_dict(self.base_dict)
        self.assertEqual("resistor", resistor.table)

    def test_resistor_values_correct(self):
        self._setup_resistor()
        resistor = component.create_component_from_dict(self.base_dict)
        for k in self.base_dict.keys():
            self.assertEqual(self.base_dict[k], resistor.columns[k])


class TestFromDigikeyPart(unittest.TestCase):
    @staticmethod
    def expected_from_csv(csvpath):
        with open(csvpath, "r") as infile:
            reader = csv.DictReader(infile)
            return component.create_component_from_dict(next(reader))

    def test_resistor_from_digikey(self):
        mock_part = MagicMock()
        mock_part.limited_taxonomy.value = "Resistors"
        mock_part.primary_datasheet = (
                "https://www.yageo.com/upload/media/product/productsearch/"
                "datasheet/rchip/PYu-RT_1-to-0.01_RoHS_L_15.pdf")
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

        actual = component.create_component_from_digikey_part(mock_part)
        expected = self.expected_from_csv("sample_parts_csv/YAG2320CT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def test_ceramic_capacitor_from_digikey(self):
        mock_part = MagicMock()
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

        actual = component.create_component_from_digikey_part(mock_part)
        expected = self.expected_from_csv(
                "sample_parts_csv/1276-1123-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Capacitor_THT:CP_Radial_D10.0mm_H17.5mm_P5.00mm")
    def test_electrolytic_capacitor_from_digikey(self, mock_input):
        mock_part = MagicMock()
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

        actual = component.create_component_from_digikey_part(mock_part)
        expected = self.expected_from_csv(
                "sample_parts_csv/493-13313-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Capacitor_THT:C_Radial_D6.30mm_H12.2mm_P5.00mm")
    def test_unpolarized_electrolytic_capacitor_from_digikey(
            self, mock_input):
        mock_part = MagicMock()
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

        actual = component.create_component_from_digikey_part(mock_part)
        expected = self.expected_from_csv(
                "sample_parts_csv/10-ECE-A1HN100UBCT-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    @patch("partdb.component.input",
           return_value="Amplifier_Operational:LM4562")
    def test_opamp_from_digikey(self, mock_input):
        mock_part = MagicMock()
        mock_part.limited_taxonomy.value = "Integrated Circuits (ICs)"
        mock_part.limited_taxonomy.children = [
                MagicMock(
                    value=(
                        "Linear - Amplifiers - Instrumentation, OP Amps, "
                        "Buffer Amps - Amplifiers - Instrumentation, OP Amps, "
                        "Buffer Amps"))]
        mock_part.primary_datasheet = (
                "https://www.ti.com/lit/ds/snas326k/snas326k.pdf")
        mock_part.manufacturer.value = "Texas Instruments"
        mock_part.manufacturer_part_number = "LM4562MAX/NOPB"
        mock_part.digi_key_part_number = "296-35279-1-ND"
        mock_part.parameters = [
                MagicMock(parameter="Gain Bandwidth Product", value="55 MHz"),
                MagicMock(parameter="Slew Rate", value="20V/µs"),
                MagicMock(parameter="Package / Case",
                          value='8-SOIC (0.154", 3.90mm Width)'),
                MagicMock(parameter="Supplier Device Package", value="8-SOIC"),
                MagicMock(parameter="Number of Circuits", value="2"),
                ]

        actual = component.create_component_from_digikey_part(mock_part)
        expected = self.expected_from_csv(
                "sample_parts_csv/296-35279-1-ND.csv")
        self.assertEqual(expected.to_csv(), actual.to_csv())


if __name__ == "__main__":
    unittest.main()
