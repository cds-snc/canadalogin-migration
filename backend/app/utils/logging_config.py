import logging

from app.utils.correlation_id import CorrelationIdFilter

LOG_FORMAT = "%(asctime)s - %(levelname)s - [correlation_id=%(correlation_id)s attempt_id=%(attempt_id)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_level: int) -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=log_level)
        root_logger = logging.getLogger()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers:
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        if not any(
            isinstance(existing_filter, CorrelationIdFilter)
            for existing_filter in handler.filters
        ):
            handler.addFilter(CorrelationIdFilter())
