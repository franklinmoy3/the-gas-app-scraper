import argparse
import logging
from loguru import logger
import multiprocessing as mp
import sys

get_request_log_fmt_str = "Making GET request to {url}"
api_response_log_fmt_str = "Received HTTP {status_code} from {url}"
abort_due_to_bad_response_fmt_str = "Cannot continue due to receiving non-200 response"
read_html_log_fmt_str = "Reading HTML tree from {url}"
results_queue_type_error_msg = "results_queue must be a multiprocessing.queues.Queue"


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
    arg_parser.add_argument(
        "--refresh-station-list",
        action="store_true",
        default=False,
        help="Denotes whether to refresh the list of stations (for applicable franchises)",
    )
    arg_parser.add_argument(
        "--mp-pool-size",
        action="store",
        type=int,
        default=mp.cpu_count(),
        help="Number of subprocesses to use for gas station data retrieval (for applicable franchises)",
    )
    arg_parser.add_argument(
        "--no-collect-prices",
        action="store_true",
        default=False,
        help="Whether to not collect prices. Useful for if you only want to refresh data source files such as gas station URLs."
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
