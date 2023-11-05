#! /usr/bin/env python

import re
import unittest
from unittest.mock import patch

from partdb import cli

from tests.test_component import expected_component_from_csv

@unittest.skip("external API call")
class TestCreateFromDigikeyAPI(unittest.TestCase):
    def check_component_from_digikey_pn_matches_csv(self, digikey_pn):
        actual = cli.create_component_from_digikey_pn(digikey_pn)
        csv_name = re.sub(r"/", "_", f"{digikey_pn}.csv")
        expected = expected_component_from_csv(f"sample_parts_csv/{csv_name}")
        self.assertEqual(expected.to_csv(), actual.to_csv())

    def setUp(self):
        cli.setup_digikey(cli.load_config())

    def test_resistor_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("YAG2320CT-ND")

    def test_ceramic_capacitor_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("1276-1123-1-ND")

    @patch(
        "partdb.component.input",
        return_value="Capacitor_THT:CP_Radial_D10.0mm_H17.5mm_P5.00mm",
    )
    def test_electrolytic_capacitor_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("493-13313-1-ND")

    @patch(
        "partdb.component.input",
        return_value="Capacitor_THT:C_Radial_D6.30mm_H12.2mm_P5.00mm",
    )
    def test_nonpolarized_electrolytic_capacitor_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("10-ECE-A1HN100UBCT-ND")

    @patch("partdb.component.input", return_value="Amplifier_Operational:LM4562")
    def test_opamp_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("296-35279-1-ND")

    @patch("partdb.component.input", return_value="MCU_ST_STM32F0:STM32F042K4Tx")
    def test_microcontroller_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("STM32F042K4T6TR-ND")

    @patch("partdb.component.input", return_value="Regulator_Linear:LM317_TO-220")
    def test_vreg_pos_adj_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("LM317HVT/NOPB-ND")

    @patch("partdb.component.input", return_value="Regulator_Linear:LM7912_TO-220")
    def test_neg_fixed_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("LM7912CT/NOPB-ND")

    def test_diode_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("1N4148FSCT-ND")

    def test_diode_schottky_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("BAT54WS-FDICT-ND")

    def test_diode_zener_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("MMSZ5231B-FDICT-ND")

    @patch("partdb.component.input", return_value="Device:D_Dual_Series_ACK")
    def test_diode_array_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("BAV99TPMSCT-ND")

    def test_led_from_digikey_pn(self):
        self.check_component_from_digikey_pn_matches_csv("160-1445-1-ND")

    @patch(
        "partdb.component.input",
        side_effect=["Device:LED_RKBG", "LED_THT:LED_D5.0mm-4_RGB"],
    )
    def test_led_rgb_tht_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("754-1615-ND")

    @patch(
        "partdb.component.input",
        side_effect=[
            "LED:Inolux_IN-PI554FCH",
            "LED_SMD:LED_Inolux_IN-PI554FCH_PLCC4_5.0x5.0mm_P3.2mm",
        ],
    )
    def test_led_adressable_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("1830-1106-1-ND")

    @patch(
        "partdb.component.input",
        side_effect=["Device:Q_NPN_EBC", "Package_TO_SOT_THT:TO-92_Inline"],
    )
    def test_bjt_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("2N3904FS-ND")

    @patch(
        "partdb.component.input",
        side_effect=["Device:Q_NPN_QUAD_FAKE", "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"],
    )
    def test_bjt_array_from_digikey_pn(self, mock_input):
        self.check_component_from_digikey_pn_matches_csv("MMPQ3904FSCT-ND")


if __name__ == "__main__":
    unittest.main()
