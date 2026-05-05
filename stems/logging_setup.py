import logging


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("stems")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
