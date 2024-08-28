import argparse
import logging
from loguru import logger
import sys


def parse_command_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "--log-level",
        action="store",
        type=str,
        default="DEBUG",
        help="The logging level to use",
    )
    arg_parser.add_argument(
        "--structured-logging",
        action="store_true",
        default=False,
        help="Denotes whether to structure log statements",
    )
    return arg_parser.parse_args()


def configure_logger(run_args) -> logging.Logger:
    # Replace default stdout registration with the one we will configure
    logger.remove(0)
    if run_args.structured_logging:
        logger.add(sys.stdout, level=run_args.log_level, serialize=True)
    else:
        logger.add(sys.stdout, level=run_args.log_level)
    return logger
