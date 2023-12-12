#!/usr/bin/env python

import dearpygui.dearpygui as dpg
import os

from partdb import config, db

dpg.create_context()
dpg.create_viewport(title="KiCad Part Database")


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


model = Partdb_Model()


def update_component_type_display():
    dpg.configure_item(
        "component_type_list", items=model.tables, num_items=max(2, len(model.tables))
    )


def update_component_display():
    priority_cols = ["IPN", "description", "MPN"]
    dpg.delete_item("components_table", children_only=True)
    components = model.components_in_selected_tables
    for col in priority_cols:
        dpg.add_table_column(label=col, parent="components_table")
    for comp in components:
        with dpg.table_row(parent="components_table"):
            for col in priority_cols:
                dpg.add_selectable(
                    label=comp[col],
                    span_columns=True,
                    user_data=comp["IPN"],
                    callback=component_selection_callback,
                )
                # TODO: hide component when we unselect?
    dpg.configure_item("components_table", policy=dpg.mvTable_SizingStretchProp)


def update_selected_component_display():
    # TODO: add handler to text inputs to track modification
    # TODO: make this auto-select first component on loading database
    # TODO: validators for any of these? e.g. exclude_from_* are 0/1 only
    dpg.delete_item("selected_component_table", children_only=True)
    dpg.add_table_column(label="Field", parent="selected_component_table")
    dpg.add_table_column(label="Value", parent="selected_component_table")
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
    other_fields = sorted(set(model.selected_component.keys()) - set(priority_fields))
    if model.selected_component:
        for field in priority_fields + other_fields:
            with dpg.table_row(parent="selected_component_table"):
                dpg.add_text(field)
                dpg.add_input_text(
                    default_value=model.selected_component[field], width=-1
                )


def load_database():
    model.load_table_names_from_database()
    update_component_type_display()
    model.load_components_from_selected_tables()
    update_component_display()


def default_database_callback(sender, app_data):
    dpg.set_value(value=model.config_db_path, item="override_db_path")
    model.selected_db_path = dpg.get_value("override_db_path")
    load_database()


def choose_database_callback(sender, app_data, user_data):
    for file in app_data["selections"]:
        filepath = app_data["selections"][file]
        dpg.set_value(value=filepath, item=user_data)
        model.selected_db_path = dpg.get_value(user_data)
    load_database()


def component_type_selection_callback(sender, app_data):
    # load components from selected tables and populate table grid
    model.selected_table = [app_data]
    model.load_components_from_selected_tables()
    update_component_display()


def component_selection_callback(sender, app_data, user_data):
    IPN = user_data
    model.load_component_by_IPN(IPN)
    update_selected_component_display()


def show_demo_callback():
    import dearpygui.demo as demo

    demo.show_demo()


def config_setup_ok_callback(sender, app_data):
    # write values from dialog to config file, then reload the config
    config_path = dpg.get_value("config_path")
    config.make_config_file(
        config_path=config_path,
        overwrite=True,
        digikey_client_id=dpg.get_value("config_digikey_client_id"),
        digikey_client_secret=dpg.get_value("config_digikey_client_secret"),
    )
    model.load_config(config_path)

    dpg.hide_item("config_setup_window")


def config_setup_cancel_callback(sender, app_data):
    # reset values in dialog/registry to model values
    dpg.set_value(value=model.config_path, item="config_path")
    dpg.set_value(value=model.config_db_path, item="config_db_path")
    dpg.set_value(
        value=model.config_data["digikey"]["client_id"],
        item="config_digikey_client_id",
    )
    dpg.set_value(
        value=model.config_data["digikey"]["client_secret"],
        item="config_digikey_client_secret",
    )
    dpg.hide_item("config_setup_window")


def show_override_database_file_dialog_callback():
    dpg.show_item("override_database_file_dialog")


def create_file_dialog(tag, label, extensions, target_variable, callback=None):
    def file_selection_callback(sender, app_data, user_data):
        for file in app_data["selections"]:
            filepath = app_data["selections"][file]
            dpg.set_value(value=filepath, item=user_data)

    if not callback:
        callback = file_selection_callback

    with dpg.file_dialog(
        label=label,
        directory_selector=False,
        height=400,
        show=False,
        file_count=1,
        callback=callback,
        user_data=target_variable,
        tag=tag,
    ):
        for ext in extensions:
            dpg.add_file_extension(ext)


database_file_extensions = [".db", ".*"]
create_file_dialog(
    "override_database_file_dialog",
    "Choose Database",
    database_file_extensions,
    "override_db_path",
    callback=choose_database_callback,
)
create_file_dialog(
    "config_database_file_dialog",
    "Choose Database",
    database_file_extensions,
    "config_db_path",
)
create_file_dialog(
    "config_file_dialog",
    "Choose Configuration File",
    [".json", ".*"],
    "config_path",
)


with dpg.window(
    label="Configuration File Editor",
    modal=False,
    show=False,
    width=700,
    # autosize=True,
    # no_resize=False,
    pos=(100, 100),
    on_close=config_setup_cancel_callback,
    tag="config_setup_window",
):
    # TODO: when this changes, reload from the specified config file?
    with dpg.group(horizontal=True):
        dpg.add_input_text(
            tag="config_path",
            default_value=model.config_path,
        )
        dpg.add_button(
            label="Choose Configuration File",
            callback=lambda: dpg.show_item("config_file_dialog"),
        )
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_input_text(
            tag="config_db_path",
            default_value=model.config_db_path,
        )
        dpg.add_button(
            label="Choose Database",
            callback=lambda: dpg.show_item("config_database_file_dialog"),
        )
    dpg.add_separator()
    dpg.add_text("Digikey API Settings")
    dpg.add_input_text(
        label="Client ID",
        tag="config_digikey_client_id",
        default_value=model.config_data["digikey"]["client_id"],
    )
    dpg.add_input_text(
        label="Client Secret",
        tag="config_digikey_client_secret",
        default_value=model.config_data["digikey"]["client_secret"],
    )
    dpg.add_separator()
    with dpg.group(horizontal=True):
        dpg.add_button(label="Save", callback=config_setup_ok_callback)
        dpg.add_button(label="Cancel", callback=config_setup_cancel_callback)

with dpg.window(tag="primary_window"):
    with dpg.menu_bar():
        with dpg.menu(label="Setup"):
            dpg.add_menu_item(label="New Database...")  # TODO: callback
            dpg.add_menu_item(
                label="Load Database...",
                callback=show_override_database_file_dialog_callback,
            )
            dpg.add_menu_item(
                label="Edit Configuration...",
                callback=lambda: dpg.show_item("config_setup_window"),
            )
            dpg.add_menu_item(label="Show Demo...", callback=show_demo_callback)

    with dpg.group(horizontal=True):
        dpg.add_input_text(
            default_value=model.config_db_path,
            tag="override_db_path",
        )
        dpg.add_button(
            label="Choose Database",
            callback=lambda: dpg.show_item("override_database_file_dialog"),
        )
        dpg.add_button(label="Default Database", callback=default_database_callback)

    # TODO: multiselect, or try a dropdown
    # see https://github.com/hoffstadt/DearPyGui/issues/380
    # dpg.add_combo(
    #     model.tables,
    #     label="Component Types",
    #     callback=component_type_selection_callback,
    #     tag="component_type_list",
    # )
    dpg.add_listbox(
        model.tables,
        label="Component Types",
        callback=component_type_selection_callback,
        tag="component_type_list",
    )
    update_component_type_display()

    with dpg.group(horizontal=True):
        with dpg.child_window(autosize_x=False, width=500):
            dpg.add_text("Components in Selected Tables")
            dpg.add_table(
                label="Components in Selected Tables",
                header_row=True,
                pad_outerX=True,
                # policy=dpg.mvTable_SizingFixedFit,
                resizable=True,
                # hideable=True,
                # scrollX=True,
                # scrollY=True,
                # borders_innerH=False,
                # borders_innerV=False,
                no_host_extendX=True,
                borders_outerH=True,
                borders_outerV=True,
                # row_background=True,  # this makes it impossible to see the selection
                tag="components_table",
            )
            update_component_display()
        with dpg.child_window(autosize_x=True):
            dpg.add_text("Selected Component")
            dpg.add_table(
                label="Selected Component",
                header_row=True,
                resizable=True,
                scrollY=True,
                borders_outerH=True,
                borders_outerV=True,
                tag="selected_component_table",
            )
            update_selected_component_display()

    # for n, error in enumerate(model.init_errors):
    #     print(error)
    #     tag = f"partdb_error_popup{n}"
    #     with dpg.window(
    #         label="Partdb Error",
    #         modal=True,
    #         autosize=True,
    #         pos=(200,200),
    #         tag=tag,
    #     ):
    #         dpg.add_text(error)
    #         dpg.add_separator()
    #         with dpg.group(horizontal=True):
    #             def close_callback():
    #                 dpg.configure_item(tag, show=False)
    #             dpg.add_button(label="OK", callback=close_callback)
    #             dpg.add_button(label="Cancel", callback=close_callback)

    if model.config_file_error:
        dpg.show_item("config_setup_window")
        dpg.focus_item("config_setup_window")

    with dpg.window(
        label="Partdb Error",
        autosize=True,
        pos=(200, 200),
        show=False,
        tag="error_popup",
    ):
        # TODO: make OK open configuration file editor?
        dpg.add_text(
            f"Invalid database path in configuration file: '{model.config_db_path}'"
        )
        dpg.add_separator()
        with dpg.group(horizontal=True):

            def close_callback():
                dpg.configure_item("error_popup", show=False)

            dpg.add_button(label="OK", callback=close_callback)
            dpg.add_button(label="Cancel", callback=close_callback)
    if model.config_db_path_error and not model.config_file_error:
        dpg.show_item("error_popup")
        dpg.focus_item("error_popup")

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("primary_window", True)
dpg.start_dearpygui()
dpg.destroy_context()
