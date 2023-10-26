#! /usr/bin/env python

import csv
import re
import unittest
from unittest.mock import patch, MagicMock

from partdb import component
from partdb.component import (Component, Resistor, Capacitor, Microcontroller,
                              LED)


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
                ("2-LCC", "2-LCC"),
                ("A1234", "A1234"),
                ]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(
                        expected, Component.process_smd_package(package))

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
        testcases = [
                ("48", "48-LQFP")
                ]
        for expected, package in testcases:
            with self.subTest(Package=package):
                self.assertEqual(expected,
                                 Microcontroller.process_pincount(package))

    def test_process_core(self):
        testcases = [
                ("ARM Cortex-M0", "ARM® Cortex®-M0")
                ]
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
                self.assertEqual(expected,
                                 LED.process_led_dimension(dimension))


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
    """Base class for testing Component.from_digikey() methods."""
    @staticmethod
    def init_mock(category, datasheet, mfg, MPN, digikey_PN,
                  subcategory=None, family=None, parameters={}):
        mock_part = MagicMock()
        mock_part.limited_taxonomy.value = category
        if subcategory:
            mock_part.limited_taxonomy.children = [
                    MagicMock(value=subcategory)]
        if family:
            mock_part.family.value = family
        mock_part.primary_datasheet = datasheet
        mock_part.manufacturer.value = mfg
        mock_part.manufacturer_part_number = MPN
        mock_part.digi_key_part_number = digikey_PN
        mock_part.parameters = [MagicMock(parameter=k, value=parameters[k])
                                for k in parameters]
        return mock_part

    def check_component_matches_csv(self, mock_part):
        """Check that the component created from the mock digikey API response
        object matches the golden CSV corresponding to the mock's digikey PN.
        """
        actual = component.create_component_from_digikey_part(mock_part)
        digikey_pn = mock_part.digi_key_part_number
        csv_name = re.sub(r"/", "_", f"{digikey_pn}.csv")
        expected = expected_component_from_csv(f"sample_parts_csv/{csv_name}")
        self.assertEqual(expected.to_csv(), actual.to_csv())


class TestResistorFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_resistor_mock(resistance, tolerance, power, composition, package,
                           **kwargs):
        parameters = {
                "Resistance": resistance,
                "Tolerance": tolerance,
                "Power (Watts)": power,
                "Composition": composition,
                "Supplier Device Package": package,
                }
        s = super(TestResistorFromDigikeyPart, TestResistorFromDigikeyPart)
        return s.init_mock(
                category="Resistors", parameters=parameters, **kwargs)

    def test_resistor_from_digikey(self):
        mock_part = self.init_resistor_mock(
                resistance="100Ω",
                tolerance="±1%",
                power="0.1W",
                composition="Thin Film",
                package="0603",
                datasheet=(
                    "https://www.yageo.com/upload/media/product/productsearch/"
                    "datasheet/rchip/PYu-RT_1-to-0.01_RoHS_L_15.pdf"),
                mfg="YAGEO",
                MPN="RT0603FRE07100RL",
                digikey_PN="YAG2320CT-ND")
        self.check_component_matches_csv(mock_part)


class TestCapacitorFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_capacitor_mock(capacitance, tolerance, voltage, package, family,
                            tempco=None, polarization=None, package_size=None,
                            height=None, lead_spacing=None, **kwargs):
        parameters = {
                "Capacitance": capacitance,
                "Tolerance": tolerance,
                "Voltage - Rated": voltage,
                "Package / Case": package,
                }
        if tempco:
            parameters["Temperature Coefficient"] = tempco
        if polarization:
            parameters["Polarization"] = polarization
        if package_size:
            parameters["Size / Dimension"] = package_size
        if height:
            parameters["Height - Seated (Max)"] = height
        if lead_spacing:
            parameters["Lead Spacing"] = lead_spacing

        s = super(TestCapacitorFromDigikeyPart, TestCapacitorFromDigikeyPart)
        return s.init_mock(
            category="Capacitors", family=family,
            parameters=parameters, **kwargs)

    def test_ceramic_capacitor_from_digikey(self):
        mock_part = self.init_capacitor_mock(
                family="Ceramic Capacitors",
                datasheet=(
                    "https://mm.digikey.com/Volume0/opasdata/d220001/medias/"
                    "docus/1068/CL21B334KBFNNNE_Spec.pdf"),
                mfg="Samsung Electro-Mechanics",
                MPN="CL21B334KBFNNNE",
                digikey_PN="1276-1123-1-ND",
                capacitance="0.33 µF",
                tolerance="±10%",
                voltage="50V",
                tempco="X7R",
                package="0805 (2012 Metric)",
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           return_value="Capacitor_THT:CP_Radial_D10.0mm_H17.5mm_P5.00mm")
    def test_electrolytic_capacitor_from_digikey(self, mock_input):
        mock_part = self.init_capacitor_mock(
                family="Aluminum Electrolytic Capacitors",
                datasheet=(
                    "https://www.nichicon.co.jp/english/series_items/"
                    "catalog_pdf/e-ucy.pdf"),
                mfg="Nichicon",
                MPN="UCY2G100MPD1TD",
                digikey_PN="493-13313-1-ND",
                capacitance="10 µF",
                tolerance="±20%",
                voltage="400V",
                package="Radial, Can",
                polarization="Polar",
                package_size='0.394" Dia (10.00mm)',
                height='0.689" (17.50mm)',
                lead_spacing='0.197" (5.00mm)',
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           return_value="Capacitor_THT:C_Radial_D6.30mm_H12.2mm_P5.00mm")
    def test_unpolarized_electrolytic_capacitor_from_digikey(
            self, mock_input):
        mock_part = self.init_capacitor_mock(
                family="Aluminum Electrolytic Capacitors",
                datasheet=(
                    "https://industrial.panasonic.com/cdbs/www-data/pdf/"
                    "RDF0000/ABA0000C1053.pdf"),
                mfg="Panasonic Electronic Components",
                MPN="ECE-A1HN100UB",
                digikey_PN="10-ECE-A1HN100UBCT-ND",
                capacitance="10 µF",
                tolerance="±20%",
                voltage="50V",
                package="Radial, Can",
                polarization="Bi-Polar",
                package_size='0.248" Dia (6.30mm)',
                height='0.480" (12.20mm)',
                lead_spacing='0.197" (5.00mm)',
                )
        self.check_component_matches_csv(mock_part)


class TestOpAmpFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_opamp_mock(bandwidth, slewrate, package, short_package, num_units,
                        **kwargs):
        parameters = {
                "Gain Bandwidth Product": bandwidth,
                "Slew Rate": slewrate,
                "Package / Case": package,
                "Supplier Device Package": short_package,
                "Number of Circuits": num_units,
                }

        s = super(TestOpAmpFromDigikeyPart, TestOpAmpFromDigikeyPart)
        return s.init_mock(
            category="Integrated Circuits (ICs)", subcategory=(
                "Linear - Amplifiers - Instrumentation, OP Amps, Buffer Amps "
                "- Amplifiers - Instrumentation, OP Amps, Buffer Amps"),
            parameters=parameters, **kwargs)

    @patch("partdb.component.input",
           return_value="Amplifier_Operational:LM4562")
    def test_opamp_from_digikey(self, mock_input):
        mock_part = self.init_opamp_mock(
                datasheet="https://www.ti.com/lit/ds/snas326k/snas326k.pdf",
                mfg="Texas Instruments", MPN="LM4562MAX/NOPB",
                digikey_PN="296-35279-1-ND",
                bandwidth="55 MHz",
                slewrate="20V/µs",
                package='8-SOIC (0.154", 3.90mm Width)',
                short_package="8-SOIC",
                num_units="2",
                )
        self.check_component_matches_csv(mock_part)


class TestMicrocontrollerFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_microcontroller_mock(core, speed, package, **kwargs):
        parameters = {
                "Core Processor": core,
                "Speed": speed,
                "Supplier Device Package": package,
                }

        s = super(TestMicrocontrollerFromDigikeyPart,
                  TestMicrocontrollerFromDigikeyPart)
        return s.init_mock(
            category="Integrated Circuits (ICs)",
            subcategory="Embedded - Microcontrollers - Microcontrollers",
            parameters=parameters, **kwargs)

    @patch("partdb.component.input",
           return_value="MCU_ST_STM32F0:STM32F042K4Tx")
    def test_microcontroller_from_digikey(self, mock_input):
        mock_part = self.init_microcontroller_mock(
                datasheet=("https://www.st.com/resource/en/datasheet/"
                           "stm32f042k4.pdf"),
                mfg="STMicroelectronics", MPN="STM32F042K4T6TR",
                digikey_PN="STM32F042K4T6TR-ND",
                core="ARM® Cortex®-M0",
                package="32-LQFP (7x7)",
                speed="48MHz",
                )
        self.check_component_matches_csv(mock_part)


class TestVRegFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_vreg_mock(vout_min, vout_max, vin_max, iout, output_type, package,
                       **kwargs):
        parameters = {
                "Supplier Device Package": package,
                "Voltage - Output (Min/Fixed)": vout_min,
                "Voltage - Output (Max)": vout_max,
                "Voltage - Input (Max)": vin_max,
                "Current - Output": iout,
                "Output Type": output_type,
                }

        s = super(TestVRegFromDigikeyPart, TestVRegFromDigikeyPart)
        return s.init_mock(
            category="Integrated Circuits (ICs)",
            subcategory=(
                "Power Management (PMIC) - Voltage Regulators - Linear, "
                "Low Drop Out (LDO) Regulators - Voltage Regulators - "
                "Linear, Low Drop Out (LDO) Regulators"),
            parameters=parameters, **kwargs)

    @patch("partdb.component.input",
           return_value="Regulator_Linear:LM317_TO-220")
    def test_vreg_pos_adj_from_digikey(self, mock_input):
        mock_part = self.init_vreg_mock(
                datasheet=(
                    "https://www.ti.com/general/docs/suppproductinfo.tsp?"
                    "distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com%2Flit%2Fgpn"
                    "%2Flm117hv"),
                mfg="Texas Instruments", MPN="LM317HVT/NOPB",
                digikey_PN="LM317HVT/NOPB-ND",
                    package="TO-220-3",
                    vout_min="1.25V",
                    vout_max="57V",
                    vin_max="60V",
                    iout="1.5A",
                    output_type="Adjustable",
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           return_value="Regulator_Linear:LM7912_TO-220")
    def test_vreg_neg_fixed_from_digikey(self, mock_input):
        mock_part = self.init_vreg_mock(
                datasheet=(
                    "https://www.ti.com/general/docs/suppproductinfo.tsp?"
                    "distId=10&gotoUrl=https%3A%2F%2Fwww.ti.com"
                    "%2Flit%2Fgpn%2Flm79"),
                mfg="Texas Instruments", MPN="LM7912CT/NOPB",
                digikey_PN="LM7912CT/NOPB-ND",
                package="TO-220-3",
                vout_min="-12V",
                vout_max="-",
                vin_max="-35V",
                iout="1.5A",
                output_type="Fixed",
                )
        self.check_component_matches_csv(mock_part)


class TestDiodeFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_diode_mock(reverse_voltage, package, current_or_power,
                        diode_type=None, diode_configuration="", **kwargs):
        parameters = {
                "Supplier Device Package": package,
                }
        if diode_configuration:
            parameters["Diode Configuration"] = diode_configuration
        if diode_type in ("Standard", "Schottky"):
            parameters["Voltage - DC Reverse (Vr) (Max)"] = reverse_voltage
            parameters["Current - Average Rectified (Io)"] = current_or_power
            parameters["Technology"] = diode_type
            subcategory = (
                "Diodes - Rectifiers - Single Diodes - Rectifiers - "
                "Single Diodes")
        else:
            parameters["Voltage - Zener (Nom) (Vz)"] = reverse_voltage
            parameters["Power - Max"] = current_or_power
            subcategory = (
                    "Diodes - Zener - Single Zener Diodes - Zener - "
                    "Single Zener Diodes")

        s = super(TestDiodeFromDigikeyPart, TestDiodeFromDigikeyPart)
        return s.init_mock(
            category="Discrete Semiconductor Products",
            subcategory=subcategory,
            parameters=parameters, **kwargs)

    def test_diode_from_digikey(self):
        mock_part = self.init_diode_mock(
                datasheet=(
                    "https://www.onsemi.com/download/data-sheet/pdf/"
                    "1n914-d.pdf"),
                mfg="onsemi", MPN="1N4148TR",
                digikey_PN="1N4148FSCT-ND",
                package="DO-35",
                reverse_voltage="100 V",
                current_or_power="200mA",
                diode_type="Standard",
                )
        self.check_component_matches_csv(mock_part)

    def test_schottky_diode_from_digikey(self):
        mock_part = self.init_diode_mock(
                datasheet=(
                    "https://www.diodes.com/assets/Datasheets/ds30098.pdf"),
                mfg="Diodes Incorporated", MPN="BAT54WS-7-F",
                digikey_PN="BAT54WS-FDICT-ND",
                package="SOD-323",
                reverse_voltage="30 V",
                current_or_power="100mA",
                diode_type="Schottky",
                )
        self.check_component_matches_csv(mock_part)

    def test_zener_diode_from_digikey(self):
        mock_part = self.init_diode_mock(
                datasheet=(
                    "https://www.diodes.com/assets/Datasheets/ds18010.pdf"),
                mfg="Diodes Incorporated", MPN="MMSZ5231B-7-F",
                digikey_PN="MMSZ5231B-FDICT-ND",
                package="SOD-123",
                reverse_voltage="5.1 V",
                current_or_power="500mW",
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           return_value="Device:D_Dual_Series_ACK")
    def test_diode_array_from_digikey(self, mock_input):
        mock_part = self.init_diode_mock(
                datasheet=(
                    "https://www.mccsemi.com/pdf/Products/BAV99(SOT-23).pdf"),
                mfg="Micro Commercial Co", MPN="BAV99-TP",
                digikey_PN="BAV99TPMSCT-ND",
                package="SOT-23",
                reverse_voltage="70 V",
                current_or_power="200mA",
                diode_type="Standard",
                diode_configuration="1 Pair Series Connection",
                )
        self.check_component_matches_csv(mock_part)


class TestLEDFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_led_mock(color, diode_configuration, forward_voltage="",
                      interface="", supplier_device_package="", package="",
                      size_dimension="", **kwargs):
        parameters = {
                "Color": color,
                "Configuration": diode_configuration,
                }
        if forward_voltage:
            parameters["Voltage - Forward (Vf) (Typ)"] = forward_voltage
        if interface:
            parameters["Interface"] = interface
        if package:
            parameters["Package / Case"] = package
        if supplier_device_package:
            parameters["Supplier Device Package"] = supplier_device_package
        if size_dimension:
            parameters["Size / Dimension"] = size_dimension

        s = super(TestLEDFromDigikeyPart, TestLEDFromDigikeyPart)
        return s.init_mock(category="Optoelectronics",
                           parameters=parameters, **kwargs)

    def test_led_from_digikey(self):
        mock_part = self.init_led_mock(
                datasheet=(
                    "https://optoelectronics.liteon.com/upload/download/"
                    "DS22-2000-222/LTST-C191KFKT.pdf"),
                mfg="Lite-On Inc.", MPN="LTST-C191KFKT",
                digikey_PN="160-1445-1-ND",
                color="Orange",
                forward_voltage="2V",
                diode_configuration="Standard",
                package="0603 (1608 Metric)",
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           side_effect=["Device:LED_RKBG", "LED_THT:LED_D5.0mm-4_RGB"])
    def test_led_rgb_from_digikey(self, mock_input):
        mock_part = self.init_led_mock(
                datasheet=(
                    "https://www.KingbrightUSA.com/images/catalog/SPEC/"
                    "WP154A4SUREQBFZGC.pdf"),
                mfg="Kingbright", MPN="WP154A4SUREQBFZGC",
                digikey_PN="754-1615-ND",
                color="Red, Green, Blue (RGB)",
                forward_voltage="1.9V Red, 3.3V Green, 3.3V Blue",
                diode_configuration="Common Cathode",
                package="Radial - 4 Leads",
                supplier_device_package="T-1 3/4",
                )
        self.check_component_matches_csv(mock_part)

    @patch("partdb.component.input",
           side_effect=[
               "LED:Inolux_IN-PI554FCH",
               "LED_SMD:LED_Inolux_IN-PI554FCH_PLCC4_5.0x5.0mm_P3.2mm"])
    def test_led_adressable_from_digikey(self, mock_input):
        mock_part = self.init_led_mock(
                datasheet=(
                    "https://www.inolux-corp.com/datasheet/SMDLED/"
                    "Addressable%20LED/IN-PI554FCH.pdf"),
                mfg="Inolux", MPN="IN-PI554FCH",
                digikey_PN="1830-1106-1-ND",
                color="Red, Green, Blue (RGB)",
                diode_configuration="Discrete",
                interface="PWM",
                size_dimension="5.00mm L x 5.00mm W"
                )
        self.check_component_matches_csv(mock_part)


class TestBJTFromDigikeyPart(TestFromDigikeyPart):
    @staticmethod
    def init_bjt_mock(transistor_type, vce_max, ic_max, power_max, ft, package,
                      **kwargs):
        parameters = {
                "Transistor Type": transistor_type,
                "Voltage - Collector Emitter Breakdown (Max)": vce_max,
                "Current - Collector (Ic) (Max)": ic_max,
                "Power - Max": power_max,
                "Frequency - Transition": ft,
                "Supplier Device Package": package,
                }

        s = super(TestBJTFromDigikeyPart, TestBJTFromDigikeyPart)
        return s.init_mock(category="Discrete Semiconductor Products",
                           subcategory=(
                               "Transistors - Bipolar (BJT) - "
                               "Single Bipolar Transistors - Bipolar (BJT) - "
                               "Single Bipolar Transistors"),
                           parameters=parameters, **kwargs)

    @patch("partdb.component.input",
           side_effect=[
               "Device:Q_NPN_EBC",
               "Package_TO_SOT_THT:TO-92_Inline"])
    def test_bjt_from_digikey(self, mock_input):
        mock_part = self.init_bjt_mock(
                datasheet="https://www.onsemi.com/pdf/datasheet/pzt3904-d.pdf",
                mfg="onsemi", MPN="2N3904BU",
                digikey_PN="2N3904FS-ND",
                transistor_type="NPN",
                vce_max="40 V",
                ic_max="200 mA",
                power_max="625 mW",
                ft="300MHz",
                package="TO-92-3",
                )
        self.check_component_matches_csv(mock_part)


if __name__ == "__main__":
    unittest.main()
