# kicad-database-utils

Some basic utils for creating and managing a database of electronic components,
for use as a database library for KiCad.

This is likely only useful for my particular workflow.

## Setup

Use your preferred python environment management tool. With venv:

```
# create a new venv in a location of your choice, e.g. kicad-database-utils/.venv
python -m venv /path/to/new/virtual/environment
# activate the venv
source /path/to/new/virtual/environment/bin/activate
# install requirements
python -m pip install -r requirements.txt
# install this module in editable mode
python -m pip install -e .
```

## Running

Run the CLI tool as `partdb`. Usage help is available with the `--help` option.

Run the GUI tool as `partdb_gui`.

## Licensing

This tool is released under the MIT license.

The Noto Sans and Noto Sans Mono fonts are redistributed under the terms of the OFL.
