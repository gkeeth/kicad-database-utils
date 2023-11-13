import csv
import digikey
import os

from partdb.print_utils import print_error
from partdb.component import (
    create_component_from_digikey_part,
    create_component_from_dict,
)


def setup_digikey(config_data):
    """Set up environment variables and cache for digikey API calls.

    Args:
        config_data: dict of configuration data from config file.
    """
    DIGIKEY_DEFAULT_CACHE_DIR = os.path.expanduser("~/.dblib_utils_digikey_cache")

    dk_config = config_data["digikey"]
    os.environ["DIGIKEY_CLIENT_ID"] = dk_config["client_id"]
    os.environ["DIGIKEY_CLIENT_SECRET"] = dk_config["client_secret"]
    os.environ["DIGIKEY_CLIENT_SANDBOX"] = "False"

    try:
        digikey_cache_dir = os.path.expanduser(dk_config["cache_dir"])
    except KeyError:
        digikey_cache_dir = DIGIKEY_DEFAULT_CACHE_DIR

    os.environ["DIGIKEY_STORAGE_PATH"] = digikey_cache_dir
    if not os.path.isdir(digikey_cache_dir):
        os.mkdir(digikey_cache_dir)


def create_component_from_digikey_pn(digikey_pn, dump_api_response=False):
    """Create a component from a Digikey part number.

    Args:
        digikey_pn: string containing a Digikey part number
        dump_api_response: if True, print the API response object to stdout.

    Returns:
        component based on digikey_pn, or None if a component cannot be
        created from the part number.
    """
    part = digikey.product_details(digikey_pn)
    if not part:
        print_error(f"Could not get info for part {digikey_pn}")
        return None
    if dump_api_response:
        print(part)
    return create_component_from_digikey_part(part)


def create_component_list_from_digikey_pn_list(
    digikey_pn_list, dump_api_response=False
):
    """Create a list of components from a list of digikey part numbers.

    The Digikey API environment variables need to be set up before running
    this function (via setup_digikey()).

    Any part numbers that are invalid or otherwise cannot be used to create
    a component will be skipped.

    Args:
        digikey_pn_list: list of digikey part number strings.
        dump_api_response: if True, print the API response object to stdout.

    Returns:
        A list of Components corresponding to digikey part numbers.
    """

    components = []
    for pn in digikey_pn_list:
        comp = create_component_from_digikey_pn(pn, dump_api_response)
        if comp:
            components.append(comp)
    return components


def create_component_list_from_csv(csv_path):
    """Create a list of components from a CSV file. Each line must contain all
    necessary fields for the component type in question.

    Any parts that are not successfully created are ignored.

    Args:
        csv_path: path to csv file to read.

    Returns:
        A list of Components corresponding to lines in the CSV file.
    """
    components = []
    with open(csv_path, "r") as infile:
        reader = csv.DictReader(infile)
        for d in reader:
            comp = create_component_from_dict(d)
            if comp:
                components.append(comp)
    return components
