"""Utility logging untuk training dan prediksi."""

import logging
from pathlib import Path
from typing import Union


def setup_file_logger(name: str, path: Union[str, Path]) -> logging.Logger:
    """Membuat logger file tanpa menggandakan handler.

    Format log:
        YYYY-MM-DD HH:MM:SS | LEVEL | MESSAGE
    """
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
