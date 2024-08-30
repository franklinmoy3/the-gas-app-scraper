from bs4 import BeautifulSoup
import helpers
import json
from loguru import logger
import requests


def collect_all_station_data() -> list:
    pass


def get_and_normalize_data_for_station(url: str) -> str | None:
    # Must send User-Agent, else will hang
    resp = requests.get(url, headers={"User-Agent": "PostmanRuntime/7.39.1"})
    soup = BeautifulSoup(resp.text, "html5lib")
    gas_price_section = soup.find("div", attrs={"class": "gas-price-section"})
    if gas_price_section == None:
        logger.info(
            "URL {url} does not have a gas-price-section. Returning None", url=url
        )
        return None
    # Map to normalized schema
    franchise_name = "COSTCO"
    name = (
        soup.find("h1", attrs={"automation-id": "warehouseNameOutput"}).text
        + " (Costco)"
    )
    street_address = soup.find("span", attrs={"itemprop": "streetAddress"}).text
    city = soup.find("span", attrs={"itemprop": "addressLocality"}).text
    state = soup.find("span", attrs={"itemprop": "addressRegion"}).text
    postal_code = soup.find("span", attrs={"itemprop": "postalCode"}).text

    # div class gas-price-section -> multiple divs -> span class gas-type (gas grade), other span is price with currency symbol
    regular_price = None
    mid_grade_price = None
    premium_price = None
    diesel_price = None
    for gas_price in gas_price_section.find_all("div"):
        grade = None
        price = None
        for meaningful_descendant in gas_price.find_all("span"):
            if (
                grade == None
                and "gas-type" in meaningful_descendant.get_attribute_list("class")
            ):
                grade = meaningful_descendant.text
            else:
                price = meaningful_descendant.text
        match grade:
            case "Regular":
                regular_price = price
            case "Premium":
                premium_price = price
            case "Diesel":
                diesel_price = price
            case _:
                logger.warning(
                    'Gas price with grade name "{grade_name}" is unexpected. Gas price is={gas_price}',
                    grade_name=grade,
                    gas_price=price,
                )
    if (
        regular_price == None
        and mid_grade_price == None
        and premium_price == None
        and diesel_price == None
    ):
        logger.warning(
            'URL "{url}" has a gas prices section, but no gas prices were found.',
            url=url,
        )
    return json.dumps(
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


def get_data() -> list:
    pass


def main():
    data = get_data()
    logger.info(
        get_and_normalize_data_for_station(
            "https://www.costco.com/warehouse-locations/santa-cruz-ca-149.html"
        )
    )


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main()
