import json
import os

CONFIG_FILENAME = os.path.expanduser("~/.dblib_utils_config.json")

config_data = None


def load_config():
    """Load configuration file into `config_data` dict ad return it."""
    with open(CONFIG_FILENAME, "r") as f:
        global config_data
        config_data = json.load(f)

    return config_data
