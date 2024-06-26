import os

from partdb import config, db
from partdb.component import Component, create_component_from_dict
from partdb.component import friendly_name_to_component_type, table_to_component_type


class Partdb_Model:
    def __init__(self, config_path=None):
        self.config_file_error = True
        self.config_db_path_error = True
        self.config_data = {}
        if not config_path:
            config_path = config.DEFAULT_CONFIG_PATH
        self.config_path = config_path
        self.config_db_path = ""
        self.load_config()
        self.selected_db_path = self.config_db_path
        self.load_components_from_database()

    def load_config(self, override_config_path=None):
        if override_config_path:
            config_path = os.path.abspath(os.path.expanduser(override_config_path))
        else:
            config_path = self.config_path

        try:
            config.load_config(config_path)
            # only set if config_path is valid
            self.config_path = config_path
            self.config_file_error = False
        except FileNotFoundError:
            self.config_file_error = True

        self.config_data = config.config_data
        db_path = self.config_data["db"]["path"]
        if db_path:
            # only do this if we have a non-empty path, because it's useful
            # to maintain the empty path for error messages, etc.
            db_path = os.path.abspath(
                os.path.expanduser(self.config_data["db"]["path"])
            )
            con = db.connect_to_database(db_path)
            if con:
                self.config_db_path = db_path
                self.config_db_path_error = False
                return
        self.config_db_path = db_path
        self.config_db_path_error = True

    def get_table_friendly_names(self):
        return [table_to_component_type[table].friendly_name for table in self.tables]

    def get_components_in_selected_tables(self):
        return [
            self.components[table][comp]
            for table in sorted(self.selected_table)
            for comp in sorted(self.components[table])
        ]

    def create_new_database(self, path):
        """Create and select new database. Path must not exist prior to this
        function (must be checked externally).
        """
        db.initialize_database(path)
        self.selected_db_path = path

    def _select_first_component_in_selected_table(self):
        if self.selected_table:
            components_in_table = self.components[sorted(self.selected_table)[0]]
            if components_in_table:
                first_IPN = sorted(components_in_table.keys())[0]
                self.selected_component = components_in_table[first_IPN]

    def load_components_from_database(self):
        con = db.connect_to_database(self.selected_db_path)
        self.tables = []
        self.selected_table = []
        self.components = {}
        self.selected_component = {}
        self.modified_components = {}
        if con:
            self.components = db.dump_database_to_nested_dict(con)
            self.tables = list(self.components.keys())
            if self.tables:
                self.selected_table = [self.tables[0]]
                self._select_first_component_in_selected_table()

    def select_component_by_IPN(self, IPN):
        self.selected_component = next(
            (
                c
                for c in self.get_components_in_selected_tables()
                if c.get("IPN") == IPN
            ),
            {},
        )

    def select_table(self, table_friendly_name):
        self.selected_table = [
            friendly_name_to_component_type[table_friendly_name].table
        ]
        self._select_first_component_in_selected_table()

    def modify_component(self, field_name, new_value):
        IPN = self.selected_component["IPN"]
        if field_name in Component.true_false_fields:
            new_value = int(new_value)
        if IPN not in self.modified_components:
            self.modified_components[IPN] = (
                self.selected_table[0],
                dict(self.selected_component),
            )
        self.modified_components[IPN][1][field_name] = new_value
        if self.modified_components[IPN][1] == self.selected_component:
            # if the modification takes the modified component back in line with
            # the original unmodified component, remove it from the collection of
            # modified components
            del self.modified_components[IPN]

    def is_checkbox_field(self, field):
        return field in Component.true_false_fields

    def get_component_data_for_display(self):
        priority_fields = [
            "IPN",
            "description",
            "keywords",
            "datasheet",
            "kicad_symbol",
            "kicad_footprint",
            "manufacturer",
            "exclude_from_bom",
            "exclude_from_board",
            "MPN",
            "distributor1",
            "DPN1",
            "distributor2",
            "DPN2",
        ]
        other_fields = sorted(
            set(self.selected_component.keys()) - set(priority_fields)
        )
        fields = priority_fields + other_fields
        # if there's no component loaded, we still show the priority (common)
        # fields, but we make them read-onlly
        enabled = bool(self.selected_component)
        # if the component has been modified previously, load the modified version
        IPN = self.selected_component.get("IPN")
        if IPN in self.modified_components:
            component = self.modified_components[IPN][1]
        else:
            component = self.selected_component

        return fields, component, enabled

    def save_component(self, IPN):
        # TODO: this won't work for new components that don't have IPNs yet
        con = db.connect_to_database(self.selected_db_path)
        comp = create_component_from_dict(self.modified_components[IPN][1])
        db.add_component_to_db(con, comp, update=IPN)
        table = self.modified_components[IPN][0]
        self.components[table][IPN] = self.modified_components[IPN][1]
        self.select_component_by_IPN(IPN)
        del self.modified_components[IPN]

    def save_all_components(self):
        for IPN in list(self.modified_components.keys()):
            self.save_component(IPN)
