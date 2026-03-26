import logging
import os
import sys
from pathlib import Path

LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).resolve().parent.parent / "log"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s"

# stdout handler
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setLevel(logging.DEBUG)
_stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# file handler — single app.log capturing everything
_file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# configure root logger
logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(_stream_handler)
logging.root.addHandler(_file_handler)
