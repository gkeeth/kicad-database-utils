import os

from partdb import config, db


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
        self.load_table_names_from_database()
        self.load_components_from_selected_tables()

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
        path = self.config_data["db"]["path"]
        if path:
            # only do this if we have a non-empty path, because it's useful
            # to maintain the empty path for error messages, etc.
            path = os.path.abspath(os.path.expanduser(self.config_data["db"]["path"]))
            con = db.connect_to_database(path)
            if con:
                self.config_db_path = path
                self.config_db_path_error = False
                return
        self.config_db_path_error = True
        print(f"invalid database specified in config: '{path}'")

    def load_table_names_from_database(self):
        con = db.connect_to_database(self.selected_db_path)
        self.tables = []
        if con:
            self.tables = db.get_table_names(con)
        self.selected_table = []
        if self.tables:
            self.selected_table = [self.tables[0]]

    def load_components_from_selected_tables(self):
        con = db.connect_to_database(self.selected_db_path)
        self.components_in_selected_tables = []
        self.selected_component = {}
        if con:
            self.components_in_selected_tables = db.dump_database_to_dict_list(
                con, self.selected_table
            )
            if self.components_in_selected_tables:
                self.selected_component = self.components_in_selected_tables[0]

    def load_component_by_IPN(self, IPN):
        self.selected_component = next(
            (c for c in self.components_in_selected_tables if c.get("IPN") == IPN), {}
        )