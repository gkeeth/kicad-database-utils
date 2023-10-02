#! /usr/bin/env python

import unittest
import add_part
from add_part import Resistor

# TODO: add tests for
# - add_component_to_db
# - figure out how to test digikey PN -> component
#   - Component.from_digikey() for each component type
#   - digikey API calls (create_component_from_digikey_pn)
#   - Component.get_digikey_common_data probably doesn't need to be tested
# - Component.to_csv()
# - Component.to_sql() - check resulting database instead?
# - Component.get_create_table_string() - check resulting table instead?


class TestResistorUtils(unittest.TestCase):
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
        self.assertEqual("10%", Resistor.process_tolerance("10%"))
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


if __name__ == "__main__":
    unittest.main()
