#!/usr/bin/env python

import dearpygui.dearpygui as dpg

dpg.create_context()
dpg.create_viewport(title="KiCad Part Database")

# import dearpygui.demo as demo
# demo.show_demo()

# with dpg.window(label="example window", width=600, height=300):
with dpg.window(tag="Primary Window"):
    dpg.add_text("Hello, world")
    dpg.add_button(label="Save")
    dpg.add_input_text(label="string", default_value="Quick Brown Fox")
    dpg.add_slider_float(label="float", default_value=0.273, max_value=1)

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.show_documentation()
dpg.show_font_manager()
dpg.set_primary_window("Primary Window", True)
dpg.start_dearpygui()
dpg.destroy_context()
