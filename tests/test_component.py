#! /usr/bin/env python

import csv
from io import StringIO
import re
import sqlite3
import unittest
from unittest.mock import patch

from partdb import component
from partdb.component import Component, Resistor, Capacitor, Microcontroller, LED, BJT

from tests import digikey_mocks


def expected_component_from_csv(csvpath):
    with open(csvpath, "r") as infile:
        reader = csv.DictReader(infile)
        return component.create_component_from_dict(next(reader))


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
        header = (
            "IPN,datasheet,description,keywords,value,package,"
            "exclude_from_bom,exclude_from_board,kicad_symbol,kicad_footprint,"
            "manufacturer,MPN,distributor1,DPN1,distributor2,DPN2,"
            "resistance,tolerance,power,composition\r\n"
        )
        values = (
            "R_test,ds,desc,kw,val,0603,0,0,sym,fp,mfg,mpn,dist1,dpn1,dist2,"
            "dpn2,10k,1%,0.125W,ThinFilm\r\n"
        )
        self.assertEqual(header, self.resistor.to_csv(body=False))
        self.assertEqual(header + values, self.resistor.to_csv())
        self.assertEqual(values, self.resistor.to_csv(header=False))

    def test_to_sql(self):
        columns = [
            "IPN",
            "datasheet",
            "description",
            "keywords",
            "value",
            "package",
            "exclude_from_bom",
            "exclude_from_board",
            "kicad_symbol",
            "kicad_footprint",
            "manufacturer",
            "MPN",
            "distributor1",
            "DPN1",
            "distributor2",
            "DPN2",
            "resistance",
            "tolerance",
            "power",
            "composition",
        ]
        column_names = ",".join(columns)
        column_keys = ":" + ", :".join(columns)
        column_string = f"resistor ({column_names}) VALUES({column_keys})"
        sql_update_expected = "INSERT OR REPLACE INTO " + column_string
        sql_noupdate_expected = "INSERT INTO " + column_string

        sql, vals = self.resistor.to_sql()
        self.assertEqual(sql_noupdate_expected, sql)
        self.assertEqual(self.base_dict, vals)

        sql, vals = self.resistor.to_sql(update=True)
        self.assertEqual(sql_update_expected, sql)
        self.assertEqual(self.base_dict, vals)

    def test_get_create_table_string(self):
        sql_expected = (
            "CREATE TABLE IF NOT EXISTS resistor("
            "IPN PRIMARY KEY, datasheet, description, keywords, "
            "value, package, exclude_from_bom, exclude_from_board, "
            "kicad_symbol, kicad_footprint, manufacturer, MPN, "
            "distributor1, DPN1, distributor2, DPN2, resistance, "
            "tolerance, power, composition)"
        )
        self.assertEqual(sql_expected, self.resistor.get_create_table_string())

    def test_already_in_db(self):
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        self.assertFalse(self.resistor.already_in_db(con))
        cur.execute(self.resistor.get_create_table_string())
        sql, vals = self.resistor.to_sql()
        cur.execute(sql, vals)
        self.assertTrue(self.resistor.already_in_db(con))


class TestComponentTypeRegistries(unittest.TestCase):
    expected_component_types = [
        component.Resistor,
        component.Capacitor,
        component.OpAmp,
        component.Microcontroller,
        component.VoltageRegulator,
        component.Diode,
        component.LED,
        component.BJT,
        component.Connector,
        component.Comparator,
        component.Switch,
        component.Graphic,
    ]

    def test_component_type_registry(self):
        self.assertEqual(
            self.expected_component_types, component.component_type_registry
        )

    def test_table_to_component_type(self):
        expected = {comp.table: comp for comp in self.expected_component_types}
        self.assertEqual(expected, component.table_to_component_type)

    def test_frendly_name_to_component_type(self):
        expected = {comp.friendly_name: comp for comp in self.expected_component_types}
        self.assertEqual(expected, component.friendly_name_to_component_type)


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
            ("1.6K", "1.6 kOhms"),
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

    def test_process_manufacturer(self):
        testcases = [
            ("Molex", "Molex"),
            ("Amphenol", "Amphenol ICC (FCI)"),
        ]
        for expected, mfg in testcases:
            self.assertEqual(expected, Component.process_manufacturer(mfg))

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
        testcases = [("ThinFilm", "ThinFilm"), ("ThinFilm", "Thin Film")]
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
                ValueError, "Unknown capacitor polarization 'test'"
            ):
                Capacitor.process_polarization("test")

    def test_process_package(self):
        testcases = [
            ("0805", "0805 (2012 Metric)"),
            ("Radial, Can", "Radial, Can"),
            ("2-LCC", "2-LCC"),
            ("A1234", "A1234"),
        ]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(expected, Component.process_smd_package(package))

    def test_capacitor_process_dimension(self):
        testcases = [
            ("5.00mm", "12.7in (5.00mm)"),
            ("10.0mm", "25.4in (10.00 mm)"),
            ("5.00mm", "5 mm"),
        ]
        for expected, dim in testcases:
            with self.subTest(Dimension=dim):
                self.assertEqual(expected, Capacitor.process_dimension(dim))

    def test_process_pincount(self):
        testcases = [("48", "48-LQFP")]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(expected, Microcontroller.process_pincount(package))

    def test_process_core(self):
        testcases = [("ARM Cortex-M0", "ARM® Cortex®-M0")]
        for expected, core in testcases:
            with self.subTest(Core=core):
                self.assertEqual(expected, Microcontroller.process_core(core))

    def test_process_led_package(self):
        testcases = [
            ("0603", "0603 (1608 Metric)"),
            ("5mm", "T-1 3/4"),
            ("2-LCC", "2-LCC"),
            ("A1234", "A1234"),
        ]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(expected, LED.process_led_package(package))

    def test_process_led_color(self):
        testcases = [
            ("Orange", "Orange"),
            ("RedGreenBlue", "Red, Green, Blue (RGB)"),
            ("YellowYellow-Green", "Yellow, Yellow-Green"),
        ]
        for expected, color in testcases:
            with self.subTest(Color=color):
                self.assertEqual(expected, LED.process_led_color(color))

    def test_process_led_dimension(self):
        testcases = [
            ("5.0x5.0mm", "5.00x5.00mm"),
            ("12.7x12.7mm", "12.70 x 12.70 mm"),
            ("5.0x5.0mm", "5.00mm L x 5.00mm W"),
            ("-", "wasdf"),
        ]
        for expected, dimension in testcases:
            with self.subTest(Dimension=dimension):
                self.assertEqual(expected, LED.process_led_dimension(dimension))

    def test_process_transistor_type(self):
        testcases = [
            ("NPN", False, "NPN"),
            ("PNP", False, "PNP"),
            ("4xNPN", True, "4 NPN (Quad)"),
            ("NPN-PNP", True, "NPN, PNP"),
            ("2xNPN", True, "2 NPN Darlington (Dual)"),
            ("4xNPN-1xPNP", True, "4 NPN, 1 PNP Darlington"),
        ]
        for expected_type, expected_array, transistor_type in testcases:
            with self.subTest(TransistorType=transistor_type):
                t, a = BJT.process_transistor_type(transistor_type)
                self.assertEqual(expected_type, t)
                self.assertEqual(expected_array, a)


class TestComponentFromDict(unittest.TestCase):
    def setUp(self):
        self.base_dict = self.get_base_dict()

    def get_base_dict(self):
        return {
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
        self.base_dict["IPN"] = "R"
        self.base_dict["resistance"] = "10k"
        self.base_dict["tolerance"] = "1%"
        self.base_dict["power"] = "0.125W"
        self.base_dict["composition"] = "ThinFilm"
        self.base_dict["package"] = "0603"

    def _setup_capacitor(self):
        self.base_dict["IPN"] = "C"
        self.base_dict["capacitance"] = "100n"
        self.base_dict["tolerance"] = "20%"
        self.base_dict["dielectric"] = "X7R"
        self.base_dict["voltage"] = "50V"
        self.base_dict["package"] = "0603"

    def test_unknown_not_detected(self):
        self.base_dict["IPN"] = "1"  # "1" is an unused IPN prefix
        with self.assertRaisesRegex(
            NotImplementedError, "No component type to handle part '1'"
        ):
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

    def test_component_eq(self):
        self._setup_resistor()
        resistor1 = component.create_component_from_dict(self.base_dict)
        resistor2 = component.create_component_from_dict(self.base_dict)
        self.assertEqual(resistor1, resistor2)

    def test_component_eq_not_equal(self):
        self._setup_resistor()
        resistor1 = component.create_component_from_dict(self.base_dict)
        self.base_dict["resistance"] = "1k"
        resistor2 = component.create_component_from_dict(self.base_dict)
        self.assertNotEqual(resistor1, resistor2)

    def test_component_eq_different_types(self):
        self._setup_resistor()
        resistor = component.create_component_from_dict(self.base_dict)
        self._setup_capacitor()
        capacitor = component.create_component_from_dict(self.base_dict)
        self.assertNotEqual(resistor, capacitor)


class TestFromDigikeyPart(unittest.TestCase):
    """Base class for testing Component.from_digikey() methods."""

    def check_component_matches_csv(self, mock_part):
        """Check that the component created from the mock digikey API response
        object matches the golden CSV corresponding to the mock's digikey PN.
        """
        actual = component.create_component_from_digikey_part(mock_part)
        digikey_pn = mock_part.digi_key_part_number
        csv_name = re.sub(r"/", "_", f"{digikey_pn}.csv")
        expected = expected_component_from_csv(f"sample_parts_csv/{csv_name}")
        self.assertEqual(expected, actual)


class TestResistorFromDigikeyPart(TestFromDigikeyPart):
    def test_resistor_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_resistor)

    def test_jumper_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_jumper)


class TestCapacitorFromDigikeyPart(TestFromDigikeyPart):
    def test_ceramic_capacitor_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_ceramic_capacitor)

    @patch(
        "partdb.component.input",
        return_value="Capacitor_THT:CP_Radial_D10.0mm_H17.5mm_P5.00mm",
    )
    def test_electrolytic_capacitor_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_electrolytic_capacitor)

    @patch(
        "partdb.component.input",
        return_value="Capacitor_THT:C_Radial_D6.30mm_H12.2mm_P5.00mm",
    )
    def test_unpolarized_electrolytic_capacitor_from_digikey(self, mock_input):
        self.check_component_matches_csv(
            digikey_mocks.mock_unpolarized_electrolytic_capacitor
        )


class TestOpAmpFromDigikeyPart(TestFromDigikeyPart):
    @patch("partdb.component.input", return_value="Amplifier_Operational:LM4562")
    def test_opamp_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_opamp)


class TestMicrocontrollerFromDigikeyPart(TestFromDigikeyPart):
    @patch("partdb.component.input", return_value="MCU_ST_STM32F0:STM32F042K4Tx")
    def test_microcontroller_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_microcontroller)


class TestVRegFromDigikeyPart(TestFromDigikeyPart):
    @patch("partdb.component.input", return_value="Regulator_Linear:LM317_TO-220")
    def test_vreg_pos_adj_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_vreg_pos_adj)

    @patch("partdb.component.input", return_value="Regulator_Linear:LM7912_TO220")
    def test_vreg_neg_fixed_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_vreg_neg_fixed)


class TestDiodeFromDigikeyPart(TestFromDigikeyPart):
    def test_diode_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_diode)

    def test_schottky_diode_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_schottky_diode)

    def test_zener_diode_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_zener_diode)

    @patch("partdb.component.input", return_value="Device:D_Dual_Series_ACK")
    def test_diode_array_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_diode_array)


class TestLEDFromDigikeyPart(TestFromDigikeyPart):
    def test_led_from_digikey(self):
        self.check_component_matches_csv(digikey_mocks.mock_led)

    @patch(
        "partdb.component.input",
        side_effect=["Device:LED_RKBG", "LED_THT:LED_D5.0mm-4_RGB"],
    )
    def test_led_rgb_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_rgb_led)

    @patch(
        "partdb.component.input",
        side_effect=[
            "LED:Inolux_IN-PI554FCH",
            "LED_SMD:LED_Inolux_IN-PI554FCH_PLCC4_5.0x5.0mm_P3.2mm",
        ],
    )
    def test_led_adressable_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_addressable_led)


class TestBJTFromDigikeyPart(TestFromDigikeyPart):
    @patch(
        "partdb.component.input",
        side_effect=["Device:Q_NPN_EBC", "Package_TO_SOT_THT:TO-92_Inline"],
    )
    def test_bjt_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_bjt)

    @patch(
        "partdb.component.input",
        side_effect=["Device:Q_NPN_QUAD_FAKE", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"],
    )
    def test_bjt_array_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_bjt_array)


class TestConnectorFromDigikeyPart(TestFromDigikeyPart):
    @patch(
        "partdb.component.input",
        side_effect=[
            "Connector:Conn_01x04_Pin",
            "Connector_Molex:Molex_SL_171971-0004_1x04_P2.54mm_Vertical",
        ],
    )
    def test_shrouded_connector_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_shrouded_connector)

    @patch(
        "partdb.component.input",
        side_effect=[
            "Connector:Conn_02x03_Pin",
            "Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical",
        ],
    )
    def test_unshrouded_connector_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_unshrouded_connector)

    @patch(
        "partdb.component.input",
        side_effect=[
            "Connector_Audio:AudioJack3_SwitchT",
            "Connector_Audio:Jack_3.5mm_CUI_SJ-3524-SMT_Horizontal",
        ],
    )
    def test_trs_connector_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_trs_connector)


class TestComparatorFromDigikeyPart(TestFromDigikeyPart):
    @patch(
        "partdb.component.input",
        side_effect=[
            "Comparator:LM393",
            "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        ],
    )
    def test_opencollector_comparator_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_opencollector_comparator)

    @patch(
        "partdb.component.input",
        side_effect=[
            "Comparator:MCP6561R",
            "Package_TO_SOT_SMD:SOT-23-5",
        ],
    )
    def test_pushpull_comparator_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_pushpull_comparator)


class TestSwitchFromDigikeyPart(TestFromDigikeyPart):
    @patch(
        "partdb.component.input",
        side_effect=[
            "Switch:SW_Push",
            "Button_Switch_SMD:SW_SPST_PTS645",
        ],
    )
    def test_tactile_switch_from_digikey(self, mock_input):
        self.check_component_matches_csv(digikey_mocks.mock_tactile_switch)


class TestNonDigikeyPart(unittest.TestCase):
    """
    Base class for testing Component creation for parts that don't correspond
    to "real" parts available on Digikey, like graphics.

    Components are created from a source CSV, then roundtripped back to CSV and
    compared to the original.
    """

    def check_component_csv_matches_original_csv(self, csv_name):
        """Check that the component created from the mock digikey API response
        object matches the golden CSV corresponding to the mock's digikey PN.
        """

        filename = f"sample_parts_csv/{csv_name}"
        out_csv = expected_component_from_csv(filename).to_csv()
        out_dict = next(csv.DictReader(StringIO(out_csv)))
        with open(filename, "r") as infile:
            expected_dict = next(csv.DictReader(infile))

        self.assertEqual(expected_dict, out_dict)


class TestGraphicPart(TestNonDigikeyPart):
    def test_graphic_part(self):
        self.check_component_csv_matches_original_csv("graphic_made_with_kicad.csv")


if __name__ == "__main__":
    unittest.main()
