import sys

VERBOSE = False


def set_verbose(verbose=True):
    """Set module global variable VERBOSE to value of verbose (True or False)."""
    global VERBOSE
    VERBOSE = verbose


def print_message(message, verbose=False):
    """Print a message to stdout if either the module variable VERBOSE or the
    verbose argument is True."""
    if verbose or VERBOSE:
        print(message)


def print_error(message):
    """Print a message to stderr, with "ERROR: " prepended."""
    print(f"Error: {message}", file=sys.stderr)
