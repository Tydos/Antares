import logging
import sys

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"

_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setLevel(logging.DEBUG)
_stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))

logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_stream_handler)
