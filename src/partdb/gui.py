#!/usr/bin/env python

import dearpygui.dearpygui as dpg
import os

from partdb import config
from partdb.component import Component
from partdb.gui_model import Partdb_Model

model = Partdb_Model()


def load_fonts():
    with dpg.font_registry():
        with dpg.font("NotoSans-Regular.ttf", 16, tag="sans"):
            # remap GREEK SMALL LETTER MU to MICRO
            dpg.add_char_remap(0x03BC, 0x00B5)
            dpg.bind_font("sans")
        with dpg.font("NotoSansMono-Regular.ttf", 16, tag="mono"):
            # remap GREEK SMALL LETTER MU to MICRO
            dpg.add_char_remap(0x03BC, 0x00B5)


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

    rows = []
    for comp in components:
        row_tag = None
        modified = comp["IPN"] in model.modified_components
        with dpg.table_row(parent="components_table"):
            for col in priority_cols:
                label = comp[col]
                if modified and col == "IPN":
                    label = "* " + label
                    # TODO: make this bold or more obvious somehow?
                tag = dpg.add_selectable(
                    label=label,
                    span_columns=True,
                    user_data=rows,
                    callback=component_selection_callback,
                )
                dpg.bind_item_font(item=tag, font="mono")
                # each column's selectable gets assigned its own tag, but
                # because we use span_columns, the overall row tag corresponds
                # to the first tag.
                if not row_tag:
                    row_tag = tag
        rows.append((comp["IPN"], row_tag))

    dpg.configure_item("components_table", policy=dpg.mvTable_SizingStretchProp)


def component_field_modified_callback(caller, app_data, user_data):
    IPN = model.selected_component["IPN"]
    field_name = user_data
    new_value = app_data
    if field_name in Component.true_false_fields:
        new_value = int(new_value)
    if IPN not in model.modified_components:
        model.modified_components[IPN] = dict(model.selected_component)
        update_component_display()
    model.modified_components[IPN][field_name] = new_value
    if model.modified_components[IPN] == model.selected_component:
        del model.modified_components[IPN]
        update_component_display()


def update_selected_component_display():
    # TODO: make save/reset buttons work
    # TODO: prompt to save changes when exiting/loading new database/loading new table?/etc
    # TODO: make this auto-select first component on loading database
    # TODO: add buttons to pick symbols/footprints
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
    # we still show the priority (common) fields when we don't have a
    # component loaded, but we make them read-only
    enabled = bool(model.selected_component)
    # if the component has been modified previously, load the modified version
    IPN = model.selected_component.get("IPN")
    if IPN in model.modified_components:
        component = model.modified_components[IPN]
    else:
        component = model.selected_component
    for field in priority_fields + other_fields:
        with dpg.table_row(parent="selected_component_table"):
            dpg.add_text(field)
            if field in Component.true_false_fields:
                dpg.add_checkbox(
                    default_value=bool(component.get(field, 0)),
                    enabled=enabled,
                    callback=component_field_modified_callback,
                    user_data=field,
                )
            else:
                input_tag = dpg.add_input_text(
                    default_value=component.get(field, ""),
                    width=-1,
                    enabled=enabled,
                    callback=component_field_modified_callback,
                    user_data=field,
                )
                if field == "IPN":
                    # IPN is always read-only
                    dpg.configure_item(input_tag, enabled=False)
                dpg.bind_item_font(item=input_tag, font="mono")


def load_database():
    model.modified_components = {}
    model.load_table_names_from_database()
    update_component_type_display()
    model.load_components_from_selected_tables()
    update_component_display()
    update_selected_component_display()


def default_database_callback(sender, app_data):
    dpg.set_value(value=model.config_db_path, item="override_db_path")
    model.selected_db_path = dpg.get_value("override_db_path")
    load_database()


def create_database_callback(sender, app_data, user_data):
    filepath = app_data["file_path_name"]
    if not os.path.exists(filepath):
        dpg.set_value(value=filepath, item=user_data)
        model.create_new_database(filepath)
        load_database()
    else:
        # we could show an error here
        dpg.show_item(sender)


def choose_database_callback(sender, app_data, user_data):
    if app_data["file_path_name"]:
        filepath = app_data["file_path_name"]
    for file in app_data["selections"]:
        filepath = app_data["selections"][file]
    if os.path.exists(filepath):
        dpg.set_value(value=filepath, item=user_data)
        model.selected_db_path = dpg.get_value(user_data)
        load_database()
    else:
        # it'd be better to not clear the filename field. Possible to set the
        # filename again? Or move the file exists check to the OK callback?
        dpg.show_item(sender)


def component_type_selection_callback(sender, app_data):
    # load components from selected tables and populate table grid
    model.selected_table = [app_data]
    model.load_components_from_selected_tables()
    update_component_display()
    update_selected_component_display()


def component_selection_callback(sender, app_data, user_data):
    """On selection of a component in the component list, deselect all the other
    components, load the selected component into the model, and display it in
    the component editor.

    user_data is a list of tuples of (IPN for row, tag of selectable widget for row)
    """
    for IPN, row in user_data:
        if row != sender:
            # deselect other rows in the table
            dpg.set_value(row, False)
        else:
            desired_IPN = IPN
    model.load_component_by_IPN(desired_IPN)
    update_selected_component_display()


def show_demo_callback():
    import dearpygui.demo as demo

    demo.show_demo()


def show_config_editor():
    dpg.show_item("config_setup_window")
    dpg.focus_item("config_setup_window")


def config_setup_ok_callback(sender, app_data):
    """Write values from dialog to config file, then reload the config and hide
    window.
    """
    config_path = dpg.get_value("config_path")
    config.make_config_file(
        config_path=config_path,
        overwrite=True,
        digikey_client_id=dpg.get_value("config_digikey_client_id"),
        digikey_client_secret=dpg.get_value("config_digikey_client_secret"),
        db_path=dpg.get_value("config_db_path"),
    )
    model.load_config(config_path)
    handle_model_errors()
    dpg.hide_item("config_setup_window")


def config_setup_cancel_callback(sender, app_data):
    """reset values in dialog/registry to model values, then hide window."""
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


def show_create_database_file_dialog_callback():
    dpg.show_item("create_database_file_dialog")


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
        default_filename="",
        callback=callback,
        user_data=target_variable,
        tag=tag,
    ):
        for ext in extensions:
            dpg.add_file_extension(ext)


def create_config_editor_dialog():
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


def create_db_path_error_dialog(db_path):
    with dpg.window(label="Partdb Error", autosize=True, pos=(200, 200)) as tag:
        dpg.add_text(f"Invalid database path in configuration file: '{db_path}'")
        dpg.add_text("Edit configuration file now?")
        dpg.add_separator()
        with dpg.group(horizontal=True):

            def close_callback():
                dpg.configure_item(tag, show=False)

            def ok_callback():
                show_config_editor()
                close_callback()

            dpg.add_button(label="OK", callback=ok_callback)
            dpg.add_button(label="Cancel", callback=close_callback)


def handle_model_errors():
    if model.config_file_error:
        show_config_editor()
    if model.config_db_path_error and not model.config_file_error:
        create_db_path_error_dialog(model.config_db_path)


def create_main_window():
    with dpg.window(tag="primary_window"):
        with dpg.menu_bar():
            with dpg.menu(label="Setup"):
                dpg.add_menu_item(
                    label="New Database...",
                    callback=show_create_database_file_dialog_callback,
                )
                dpg.add_menu_item(
                    label="Load Database...",
                    callback=show_override_database_file_dialog_callback,
                )
                dpg.add_menu_item(
                    label="Edit Configuration...",
                    callback=show_config_editor,
                )
                dpg.add_menu_item(label="Show Demo...", callback=show_demo_callback)

        with dpg.group(horizontal=True):
            dpg.add_input_text(
                default_value=model.config_db_path,
                tag="override_db_path",
            )
            dpg.add_button(
                label="Choose Database",
                callback=show_override_database_file_dialog_callback,
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
        # TODO: check if we need to update the selected component when the table
        # changes, so that we aren't trying to update a component that has been
        # unloaded by the model
        dpg.add_text("Component Types")
        dpg.add_listbox(
            model.tables,
            callback=component_type_selection_callback,
            tag="component_type_list",
        )
        update_component_type_display()

        with dpg.group(horizontal=True):
            with dpg.child_window(autosize_x=False, width=500):
                dpg.add_text("Components in Selected Table")
                dpg.add_table(
                    header_row=True,
                    resizable=True,
                    no_host_extendX=True,
                    borders_outerH=True,
                    borders_outerV=True,
                    tag="components_table",
                )
                update_component_display()
            with dpg.child_window(autosize_x=True):
                dpg.add_text("Selected Component")
                dpg.add_table(
                    header_row=True,
                    resizable=True,
                    borders_outerH=True,
                    borders_outerV=True,
                    tag="selected_component_table",
                )
                update_selected_component_display()
                with dpg.group(tag="button_group", horizontal=True):
                    dpg.add_button(label="Save Changes")
                    dpg.add_button(label="Discard Changes")
                    dpg.add_button(label="Add New Component")


def build_gui():
    load_fonts()

    database_file_extensions = [".db", ".*"]
    create_file_dialog(
        "create_database_file_dialog",
        "Create New Database",
        database_file_extensions,
        "override_db_path",
        callback=create_database_callback,
    )
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

    create_config_editor_dialog()
    create_main_window()
    handle_model_errors()


def main():
    dpg.create_context()
    build_gui()
    dpg.create_viewport(title="KiCad Part Database")
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


if __name__ == "__main__":
    main()
