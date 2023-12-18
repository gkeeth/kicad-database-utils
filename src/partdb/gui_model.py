import os

from partdb import config, db
from partdb.component import friendly_name_to_component_type, table_to_component_type


class Partdb_Model:
    def __init__(self):
        self.init_errors = []
        self.config_file_error = True
        self.config_db_path_error = True
        self.config_data = {}
        self.config_path = config.DEFAULT_CONFIG_PATH
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
            print(f"invalid config file specified: '{self.config_path}'")
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
        print(f"invalid database specified in config: '{db_path}'")

    def get_table_friendly_names(self):
        return [table_to_component_type[table].friendly_name for table in self.tables]

    def get_components_in_selected_tables(self):
        return [
            self.components[table][comp]
            for table in self.selected_table
            for comp in self.components[table]
        ]

    def create_new_database(self, path):
        """Create and select new database. Path must not exist prior to this
        function (must be checked externally).
        """
        db.initialize_database(path)
        self.selected_db_path = path

    def _select_first_component_in_selected_table(self):
        if self.selected_table:
            components_in_table = self.components[self.selected_table[0]]
            if components_in_table:
                first_IPN = list(components_in_table.keys())[0]
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

    def load_component_by_IPN(self, IPN):
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
