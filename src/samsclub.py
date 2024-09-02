import helpers
from helpers import results_queue_type_error_msg
import json
from loguru import logger
from multiprocessing.queues import Queue
from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By


def normalize_data(data) -> list:
    logger.info("Normalizing data...")
    normalized = []
    franchise_name = "SAMS_CLUB"
    for station in data:
        # Map to normalized schema
        name = station["name"]
        street_address = station["address"]["address1"]
        city = station["address"]["city"]
        state = station["address"]["state"]
        postal_code = station["address"]["postalCode"]
        regular_price = None
        mid_grade_price = None
        premium_price = None
        diesel_price = None
        if "gasPrices" in station:
            for gas_price in station["gasPrices"]:
                match gas_price["name"]:
                    case "UNLEAD":
                        regular_price = str(gas_price["price"])
                    case "MIDGRAD":
                        mid_grade_price = str(gas_price["price"])
                    case "PREMIUM":
                        premium_price = str(gas_price["price"])
                    case "DIESEL":
                        diesel_price = str(gas_price["price"])
                    case _:
                        logger.warning(
                            'Gas price with grade name "{grade_name}" is unexpected. Gas price object={gas_price}',
                            grade_name=gas_price["name"],
                            gas_price=gas_price,
                        )
            if (
                regular_price == None
                and mid_grade_price == None
                and premium_price == None
                and diesel_price == None
            ):
                logger.warning(
                    'Station "{name}" has a gas prices section, but no gas prices were found. Station details: {station}',
                    name=name,
                    station=station,
                )
            elif regular_price == None:
                logger.error(
                    "Expected a price for regular octane at {station_name}, but got None!",
                    station_name=name,
                )
            normalized.append(
                {
                    "franchiseName": franchise_name,
                    "name": name,
                    "streetAddress": street_address,
                    "city": city,
                    "state": state,
                    "postalCode": postal_code,
                    "regularPrice": regular_price,
                    "midGradePrice": mid_grade_price,
                    "premiumPrice": premium_price,
                    "dieselPrice": diesel_price,
                }
            )
        else:
            logger.info("Warehouse {name} does not have any gas prices", name=name)
    logger.info("Done normalizing data")
    return normalized


def get_and_normalize_data_from_source():
    logger.info("Launching Firefox in headless mode...")
    browser_opts = FirefoxOptions()
    browser_opts.add_argument("--headless")
    browser = webdriver.Firefox(options=browser_opts)
    logger.info("Started Firefox in headless mode")

    url = "view-source:https://www.samsclub.com/api/node/vivaldi/browse/v2/clubfinder/list?singleLineAddr=94040&nbrOfStores=2147483647&distance=2147483647"
    logger.info("Making browser GET request to {url}", url=url)
    browser.get(url)
    logger.info("GET request to {url} done", url=url)

    logger.info("Getting warehouse details blob from document...")
    details_blob = (
        browser.find_element(by=By.ID, value="viewsource")
        .find_element(by=By.TAG_NAME, value="pre")
        .text
    )

    logger.info("Closing Firefox and returning blob")
    browser.close()

    data = json.loads(details_blob)
    if "error" in data:
        logger.critical(
            "Data contains an error: {error} - {message}",
            error=data["error"],
            message=data["message"],
        )
        raise AssertionError("Data contains an error")
    return normalize_data(data)


def collect_data(**kwargs) -> list:
    results_queue_present = False
    if "results_queue" in kwargs:
        if isinstance(kwargs["results_queue"], Queue):
            results_queue_present = True
        else:
            raise TypeError(results_queue_type_error_msg)
    data = get_and_normalize_data_from_source()
    if results_queue_present:
        kwargs["results_queue"].put(obj=data)
        kwargs["results_queue"].close()
    logger.info("Got prices for {len_data} Sam's Club gas stations", len_data=len(data))
    return data


def main(run_args):
    if run_args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        data = collect_data()
        with open("samsclub-prices-out.json", "w") as out_file:
            out_file.write(json.dumps(data, indent=2))


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
