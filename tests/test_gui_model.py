import io
import os
import unittest
from unittest.mock import patch

from partdb import config, db
from tests.test_component import expected_component_from_csv

from partdb.gui_model import Partdb_Model


class TestGuiModel(unittest.TestCase):
    config_path = os.path.abspath("tests/test_config.json")
    db_path = os.path.abspath("tests/test_db.db")
    new_db_path = os.path.abspath("tests/test_new_db.db")

    def _cleanup_temp_files(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.new_db_path):
            os.remove(self.new_db_path)
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def setUp(self):
        self._cleanup_temp_files()
        config.make_config_file(
            config_path=self.config_path,
            db_path=self.db_path,
            digikey_client_id="fake_client_id",
            digikey_client_secret="fake_client_secret",
        )
        db.initialize_database(self.db_path)
        self.test_resistor = expected_component_from_csv(
            "sample_parts_csv/YAG2320CT-ND.csv"
        )
        self.test_capacitor = expected_component_from_csv(
            "sample_parts_csv/1276-1123-1-ND.csv"
        )
        con = db.connect_to_database(self.db_path)
        db.add_component_to_db(con, self.test_resistor)
        db.add_component_to_db(con, self.test_capacitor)
        self.model = Partdb_Model(config_path=self.config_path)

    def tearDown(self):
        self._cleanup_temp_files()

    def test_init_config_loaded_successfully(self):
        self.assertEqual(self.config_path, self.model.config_path)
        self.assertEqual(self.db_path, self.model.config_db_path)
        self.assertEqual(self.db_path, self.model.selected_db_path)
        self.assertFalse(self.model.config_file_error)
        self.assertFalse(self.model.config_db_path_error)

    def test_init_database_loaded_successfully(self):
        self.assertIn("resistor", self.model.components)
        self.assertIn("capacitor", self.model.components)
        self.assertIn("R0001", self.model.components["resistor"])
        self.assertEqual(
            self.test_resistor.columns, self.model.components["resistor"]["R0001"]
        )
        self.assertIn("C0001", self.model.components["capacitor"])
        self.assertEqual(
            self.test_capacitor.columns, self.model.components["capacitor"]["C0001"]
        )
        self.assertEqual(["capacitor", "resistor"], self.model.tables)
        self.assertEqual(["capacitor"], self.model.selected_table)
        self.assertEqual(self.test_capacitor.columns, self.model.selected_component)
        self.assertEqual({}, self.model.modified_components)

    def test_config_error(self):
        self.model.load_config("fake_config.json")
        self.assertTrue(self.model.config_file_error)

    @patch("sys.stderr", new_callable=io.StringIO)
    def test_db_error(self, mock_stderr):
        self.model.selected_db_path = "fake_db.db"
        self.model.load_components_from_database()
        self.assertEqual([], self.model.tables)
        self.assertEqual([], self.model.selected_table)
        self.assertEqual({}, self.model.components)
        self.assertEqual({}, self.model.selected_component)
        self.assertEqual({}, self.model.modified_components)
        self.assertEqual(
            (
                "Error: could not connect to database at path: "
                f"{self.model.selected_db_path}\n"
            ),
            mock_stderr.getvalue(),
        )

    def test_create_new_database(self):
        self.model.create_new_database(self.new_db_path)
        self.assertEqual(self.new_db_path, self.model.selected_db_path)
        self.assertTrue(os.path.exists(self.new_db_path))

    def test_select_table(self):
        self.model.select_table("Resistor")
        self.assertEqual(["resistor"], self.model.selected_table)

    def test_select_component_by_IPN(self):
        self.model.select_component_by_IPN("C0001")
        self.assertEqual(self.test_capacitor.columns, self.model.selected_component)

    def test_select_nonexistent_component(self):
        self.model.select_component_by_IPN("C0002")
        self.assertEqual({}, self.model.selected_component)

    def test_is_checkbox_field(self):
        self.assertTrue(self.model.is_checkbox_field("exclude_from_board"))
        self.assertTrue(self.model.is_checkbox_field("exclude_from_bom"))
        self.assertFalse(self.model.is_checkbox_field("value"))

    def test_modify_component(self):
        IPN = "C0001"
        orig_value = self.model.components["capacitor"][IPN]["value"]
        new_value = "new_value"
        self.model.modify_component("value", new_value)
        self.assertEqual(new_value, self.model.modified_components[IPN][1]["value"])
        self.assertEqual(orig_value, self.model.components["capacitor"][IPN]["value"])

        self.model.modify_component("value", orig_value)
        self.assertEqual({}, self.model.modified_components)
        self.assertEqual(orig_value, self.model.components["capacitor"][IPN]["value"])

    def test_get_component_data_for_display(self):
        self.model.select_table("Resistor")
        self.model.select_component_by_IPN("R0001")
        fields, component, enabled = self.model.get_component_data_for_display()
        self.assertEqual(["IPN", "description", "keywords"], fields[0:3])
        self.assertEqual("composition", fields[-6])
        self.assertEqual("value", fields[-1])
        self.assertEqual(self.model.components["resistor"]["R0001"], component)
        self.assertTrue(enabled)

    def test_get_component_data_for_display_modified_component(self):
        self.model.select_table("Resistor")
        self.model.select_component_by_IPN("R0001")
        self.model.modify_component("value", "new_value")
        fields, component, enabled = self.model.get_component_data_for_display()
        self.assertEqual(self.model.modified_components["R0001"][1], component)

    def test_get_component_data_for_display_no_component_loaded(self):
        self.model.select_component_by_IPN("fake_ipn")
        fields, component, enabled = self.model.get_component_data_for_display()
        self.assertEqual(["IPN", "description", "keywords"], fields[0:3])
        self.assertEqual("DPN2", fields[-1])
        self.assertEqual({}, component)
        self.assertFalse(enabled)

    def test_save_component(self):
        expected = dict(self.model.selected_component)
        expected["value"] = "new_value"
        IPN = self.model.selected_component["IPN"]
        self.model.modify_component("value", "new_value")
        self.model.save_component(IPN)
        self.assertEqual(expected, self.model.selected_component)
        self.assertEqual(expected, self.model.components["capacitor"][IPN])
        self.assertEqual({}, self.model.modified_components)

    def test_save_all_components(self):
        expected1 = dict(self.model.selected_component)
        expected1["value"] = "new_value1"
        IPN1 = self.model.selected_component["IPN"]
        self.model.modify_component("value", "new_value1")
        self.model.select_table("Resistor")
        IPN2 = "R0001"
        self.model.select_component_by_IPN(IPN2)
        expected2 = dict(self.model.selected_component)
        expected2["value"] = "new_value2"
        self.model.modify_component("value", "new_value2")
        self.model.save_all_components()
        self.assertEqual(expected1, self.model.components["capacitor"][IPN1])
        self.assertEqual(expected2, self.model.components["resistor"][IPN2])
        self.assertEqual(expected2, self.model.selected_component)
        self.assertEqual({}, self.model.modified_components)
