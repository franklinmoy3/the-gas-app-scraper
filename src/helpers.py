import argparse
from datetime import timezone
from datetime import datetime
import json
import logging
from loguru import logger
import multiprocessing as mp
import sys
import time


get_request_log_fmt_str = "Making GET request to {url}"
api_response_log_fmt_str = "Received HTTP {status_code} from {url}"
abort_due_to_bad_response_fmt_str = "Cannot continue due to receiving non-200 response"
read_html_log_fmt_str = "Reading HTML tree from {url}"
results_queue_type_error_msg = "results_queue must be a multiprocessing.queues.Queue"
user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"


def now_in_epoch_ms() -> int:
    return int(time.time() * 1000)


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
        "--cpu-pool-size",
        action="store",
        type=int,
        default=mp.cpu_count(),
        help="Number of subprocesses to use for gas station data retrieval (for applicable franchises)",
    )
    arg_parser.add_argument(
        "--no-collect-prices",
        action="store_true",
        default=False,
        help="Whether to not collect prices. Useful for if you only want to refresh data source files such as gas station URLs.",
    )
    arg_parser.add_argument(
        "--no-update-db",
        action="store_true",
        default=False,
        help="Whether to not push pricing updates to the DB. Useful for if you just want to perform testing without affecting the pricing DB",
    )
    arg_parser.add_argument(
        "--no-write-to-file",
        action="store_true",
        default=False,
        help="Whether to not write pricing update to the local filesystem. You will likely use this flag in the cloud.",
    )
    arg_parser.add_argument(
        "--use-mounted-deploy-key",
        action="store_true",
        default=False,
        help="Whether or not to use the deploy key mounted as a secret. You will likely use this flag in the cloud."
    )
    return arg_parser.parse_args()


def serialize_log(record):
    timestamp_iso = datetime.fromtimestamp(
        record["time"].timestamp(), tz=timezone.utc
    ).isoformat()
    subset = {
        "timestamp": timestamp_iso,
        "severity": record["level"].name,
        "message": record["message"],
    }
    return json.dumps(subset)


def structured_log_formatter(record):
    record["extra"]["serialized"] = serialize_log(record)
    return "{extra[serialized]}\n"


def configure_logger(run_args) -> logging.Logger:
    # Replace default stdout registration with the one we will configure
    logger.remove(0)
    if run_args.structured_logging:
        logger.add(
            sys.stdout, format=structured_log_formatter, level=run_args.log_level
        )
    else:
        logger.add(sys.stdout, level=run_args.log_level)
    return logger
