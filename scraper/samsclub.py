import helpers
import json
from loguru import logger
from selenium import webdriver
from selenium.webdriver import FirefoxOptions
from selenium.webdriver.common.by import By
import sys


def normalize_data(data) -> str:
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
                logger.warning("Station \"{name}\" has a gas prices section, but no gas prices were found. Station details: {station}", name=name, station=station)
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
    return json.dumps(normalized)


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
    normalized = normalize_data(data)
    with open("samsclub-prices-out.json", "w") as out_file:
        out_file.write(normalized)


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main()
