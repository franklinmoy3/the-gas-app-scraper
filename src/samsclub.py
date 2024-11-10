import helpers
from helpers import now_in_epoch_ms
import json
from loguru import logger
from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
import time


samsclub_us_data_source_url = "view-source:https://www.samsclub.com/api/node/vivaldi/browse/v2/clubfinder/list?singleLineAddr=94040&nbrOfStores=2147483647&distance=2147483647"


def normalize_data(data) -> list:
    logger.info("Normalizing data...")
    p_start = time.perf_counter()
    normalized = []
    franchise_name = "SAMS_CLUB"
    for station in data:
        # Map to normalized schema
        name = station["name"]
        street_address = station["address"]["address1"]
        city = station["address"]["city"]
        state = station["address"]["state"]
        postal_code = station["address"]["postalCode"]
        latitude = station["geoPoint"]["latitude"]
        longitude = station["geoPoint"]["longitude"]
        regular_price = None
        mid_grade_price = None
        premium_price = None
        diesel_price = None
        if "gasPrices" in station:
            for gas_price in station["gasPrices"]:
                match gas_price["name"]:
                    case "UNLEAD":
                        regular_price = {
                            "timestamp": now_in_epoch_ms(),
                            "price": float(gas_price["price"][0:4]),
                        }
                    case "MIDGRAD":
                        mid_grade_price = {
                            "timestamp": now_in_epoch_ms(),
                            "price": float(gas_price["price"][0:4]),
                        }
                    case "PREMIUM":
                        premium_price = {
                            "timestamp": now_in_epoch_ms(),
                            "price": float(gas_price["price"][0:4]),
                        }
                    case "DIESEL":
                        diesel_price = {
                            "timestamp": now_in_epoch_ms(),
                            "price": float(gas_price["price"][0:4]),
                        }
                    case _:
                        logger.warning(
                            '{station_name} has unexpected gas grade "{grade_name}". Gas price object={gas_price}',
                            station_name=name,
                            grade_name=gas_price["name"],
                            gas_price=gas_price,
                        )
            if (
                regular_price is None
                and mid_grade_price is None
                and premium_price is None
                and diesel_price is None
            ):
                logger.warning(
                    'Station "{station_name}" has a gas prices section, but no gas prices were found. Station details: {station}',
                    station_name=name,
                    station=station,
                )
            elif regular_price is None:
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
                    "latitude": latitude,
                    "longitude": longitude,
                    "currencySymbol": "$",
                    "regularPrice": regular_price,
                    "midGradePrice": mid_grade_price,
                    "premiumPrice": premium_price,
                    "dieselPrice": diesel_price,
                }
            )
        else:
            logger.debug("Warehouse {name} does not have any gas prices", name=name)
    p_end = time.perf_counter()
    logger.info("Done normalizing data in {time_s} s", time_s=p_end - p_start)
    return normalized


def get_and_normalize_data_from_url(url: str) -> list | None:
    p_start = time.perf_counter()
    logger.debug("Launching Firefox in headless mode...")
    browser_opts = FirefoxOptions()
    browser_opts.add_argument("--headless")
    try:
        browser = webdriver.Firefox(options=browser_opts)
    except WebDriverException as err:
        with open("geckodriver.log") as geckodriver_log:
            logger.debug(geckodriver_log.read())
        raise err
    logger.info("Started Firefox in headless mode")

    logger.debug("Making browser GET request to {url}", url=url)
    browser_get_start = time.perf_counter()
    browser.get(url)
    browser_get_end = time.perf_counter()
    logger.info(
        "GET request to {url} done in {time_s} s",
        url=url,
        time_s=browser_get_end - browser_get_start,
    )

    logger.info("Getting warehouse details blob from document...")
    details_blob = (
        browser.find_element(by=By.ID, value="viewsource")
        .find_element(by=By.TAG_NAME, value="pre")
        .text
    )

    logger.info("Closing Firefox and returning blob")
    browser.close()

    data = json.loads(details_blob)
    p_end = time.perf_counter()
    if "error" in data:
        logger.critical(
            "Data contains an error: {error} - {message}",
            error=data["error"],
            message=data["message"],
        )
        raise AssertionError("Data contains an error")
    normalized = normalize_data(data)
    logger.info(
        "Collected gas prices for all Sam's Clubs in {time_s} s", time_s=p_end - p_start
    )
    return normalized


def main(args):
    if args.refresh_station_list:
        logger.info("Sam's Club has no URL list to update")
    if args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        data = get_and_normalize_data_from_url(samsclub_us_data_source_url)
        with open("samsclub-prices-out.json", "w") as out_file:
            out_file.write(json.dumps(data, indent=2))


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
