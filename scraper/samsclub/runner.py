import json
from loguru import logger
from scraper import helpers
from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
import sys


def filter_for_gas_stations(data):
    return [
        warehouse_details
        for warehouse_details in data
        if "gasPrices" in warehouse_details
    ]


def filter_for_useful_keys(data):
    return [
        {
            "address": warehouse_details["address"],
            "gasPrices": warehouse_details["gasPrices"],
            "name": warehouse_details["name"],
        }
        for warehouse_details in data
    ]


def get_data():
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
        sys.exit(1)
    return data


def main():
    data = get_data()
    gas_stations = filter_for_gas_stations(data)
    logger.info(gas_stations)
    trimmed = filter_for_useful_keys(gas_stations)
    logger.info(trimmed)


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main()
