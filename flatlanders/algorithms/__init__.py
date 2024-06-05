from flatlanders.algorithms.flatlanders_feed import flatlanders_handler
from flatlanders.settings import FEEDGEN_URI

ALGORITHMS = {FEEDGEN_URI: flatlanders_handler}