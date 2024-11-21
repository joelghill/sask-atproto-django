from flatlanders.algorithms.flatlanders_feed import FlatlandersAlgorithm
from flatlanders.settings import FEEDGEN_URI

__FLATLANDERS = FlatlandersAlgorithm()

ALGORITHMS = {FEEDGEN_URI: __FLATLANDERS.get_feed}
