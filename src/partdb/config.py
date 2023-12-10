import json
import os
from platformdirs import user_config_dir

from partdb.print_utils import print_error, print_message

DEFAULT_CONFIG_FILENAME = "partdb.json"
DEFAULT_CONFIG_PATH = os.path.join(user_config_dir(), DEFAULT_CONFIG_FILENAME)

config_data = None


def make_config_file(
    config_path, digikey_client_id="", digikey_client_secret="", db_path=""
):
    """Create a configuration file, optionally filled with valid data.

    If a configuration file already exists at the specified path, prints an
    error and exits without modifying the existing file.

    Args:
        config_path: path to configuration file.
        digikey_client_id: digikey client ID to include in the config file.
        digikey_client_secret: digikey client secret to include in the config file.
        db_path: path to part database to include in the config file.
    """
    default_config = {
        "digikey": {
            "client_id": digikey_client_id,
            "client_secret": digikey_client_secret,
        },
        "db": {
            "path": db_path,
        },
    }

    if os.path.exists(config_path):
        print_error(f"config file already exists at {config_path}; skipping")
        return
    with open(config_path, "w") as config_file:
        json.dump(default_config, config_file)
        print_message(
            f"writing template config file to {config_path}; some data "
            "must be filled in manually"
        )


def load_config(config_path=None):
    """Load configuration file into `config_data` dict and return it.

    Also sets the module-level config_data to the data in the config file. Sets
    a valid (empty) configuration even if the config file cannot be loaded.

    Args:
        config_path: path to configuration file. If None, the default path is used.

    Returns: the configuration configuration data dict, if the config file was
        loaded successfully.
    """
    if not config_path:
        config_path = DEFAULT_CONFIG_PATH

    global config_data
    config_data = {
        "db": {"path": ""},
        "digikey": {"client_id": "", "client_secret": ""},
    }

    with open(config_path, "r") as f:
        config_data.update(json.load(f))

    return config_data
