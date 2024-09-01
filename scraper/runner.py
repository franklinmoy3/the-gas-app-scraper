from costco import collect_data as get_costco_data
import helpers
import json
from loguru import logger
from multiprocessing import Queue, Process
from samsclub import collect_data as get_sams_data


started_scraper_process_fmt_str = "Started {franchise_name} subprocess"


def get_all_prices() -> list:
    results = Queue()
    p_sams = Process(target=get_sams_data, kwargs={"results_queue": results})
    p_costco = Process(target=get_costco_data, kwargs={"results_queue": results})
    p_sams.start()
    logger.info(started_scraper_process_fmt_str, franchise_name="Sam's Club")
    p_costco.start()
    logger.info(started_scraper_process_fmt_str, franchise_name="Costco")

    prices_2d = []
    prices_2d.append(results.get())
    prices_2d.append(results.get())

    logger.info("All subprocesses joined")

    logger.info("Flattening prices into 1D array...")
    prices = [price for arr in prices_2d for price in arr]
    logger.info(
        "Done flattening prices. Read prices of {num_prices} stations",
        num_prices=len(prices),
    )
    return prices


def main():
    data = get_all_prices()
    with open("all-prices-out.json", "w") as out_file:
        out_file.write(json.dumps(data, indent=2))


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main()
