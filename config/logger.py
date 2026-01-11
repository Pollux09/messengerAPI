import logging
import sys

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)

def setup_logging(log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

logger = logging.getLogger("app")
