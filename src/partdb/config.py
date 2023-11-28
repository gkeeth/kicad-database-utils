import json
import os
from platformdirs import user_config_dir

from partdb.print_utils import print_error

DEFAULT_CONFIG_FILENAME = "partdb.json"

config_data = None


def get_config_path(config_path=None):
    """Return the system-specific path to the configuration file.

    Args:
        config_path: an optional path to a configuration file. If None, the
            default config filename in the system-default configuration file
            location is returned. If not None, config_path is returned after
            running through os.path.expanduser().

    Returns: The system-specific path to the config file, as a string.
    """
    if config_path:
        return os.path.expanduser(config_path)
    else:
        return os.path.join(user_config_dir(), DEFAULT_CONFIG_FILENAME)


def make_config_file(
    config_path=None, digikey_client_id="", digikey_client_secret="", db_path=""
):
    """Create a configuration file, optionally filled with valid data.

    If a configuration file already exists at the specified path, prints an
    error and exits without modifying the existing file.

    Args:
        config_path: path to configuration file. If None, the platform default
            location is used.
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

    config_path = get_config_path(config_path)
    if os.path.exists(config_path):
        print_error(f"config file already exists at {config_path}; skipping")
        return
    with open(config_path, "w") as config_file:
        json.dump(default_config, config_file)


def load_config(config_path=None):
    """Load configuration file into `config_data` dict and return it."""
    config_path = get_config_path(config_path)

    with open(config_path, "r") as f:
        global config_data
        config_data = json.load(f)

    return config_data
