VERBOSE = False


def set_verbose(verbose=True):
    """Set module global variable VERBOSE to value of verbose (True or False)."""
    global VERBOSE
    VERBOSE = verbose


def print_message(message, verbose=VERBOSE):
    """Print a message to stdout if global variable VERBOSE is True."""
    if verbose:
        print(message)


def print_error(message):
    """Print a message to stderr, with "ERROR: " prepended."""
    print(f"Error: {message}")
