from bs4 import BeautifulSoup
import helpers
from helpers import (
    get_request_log_fmt_str,
    api_response_log_fmt_str,
    abort_due_to_bad_response_fmt_str,
    read_html_log_fmt_str,
    user_agent,
    now_in_epoch_ms,
    convert_price_per_liter_to_price_per_gallon,
)
import json
from loguru import logger
from multiprocessing import Pool
import re
import requests
import time


costco_station_urls_file_name = "costco-gas-station-urls-us.json"
_prices_output_file_name = "costco-prices-out.json"
_should_abort = False


def write_urls_to_file(urls: list) -> None:
    with open(costco_station_urls_file_name, "w") as out_file:
        logger.info(
            "Writing Costco US warehouse URLs that have gas stations to {file_name}",
            file_name=out_file.name,
        )
        out_file.write(json.dumps(urls, indent=2))


def mark_diesel_station_urls(urls: list) -> None:
    """
    DEPRECATED

    Keep this here for historical reasons.

    It seems that Costco doesn't keep their page on diesel stations up to date.

    Instead, we'll mitigate by changing the scheduler to run near/during business hours
    to avoid running into timing conflicts for when employees are changing the prices.
    """
    diesel_stations_url = "https://www.costco.com/gasoline-diesel.html"
    logger.debug(get_request_log_fmt_str, url=diesel_stations_url)
    resp = requests.get(diesel_stations_url, headers={"User-Agent": user_agent})
    logger.info(
        api_response_log_fmt_str, status_code=resp.status_code, url=diesel_stations_url
    )

    if resp.status_code != 200:
        logger.error(abort_due_to_bad_response_fmt_str)
        resp.raise_for_status()

    logger.info(read_html_log_fmt_str, url=diesel_stations_url)
    soup = BeautifulSoup(resp.text, "html5lib")
    logger.info("Done reading HTML response tree from {url}", url=diesel_stations_url)

    # Collect stations which are reported to have diesel
    diesel_station_ids = set()
    diesel_station_addresses = set()
    station_id_from_url_regex = re.compile(r"-(\d+).html")
    for link in soup.find_all("a", href=True):
        if "/warehouse-locations/" in link["href"]:
            diesel_station_href = link["href"]
            # NOTE: Some stations have dead links, and one station has both a dead link and an incorrect address
            diesel_station_id = station_id_from_url_regex.search(
                diesel_station_href
            ).group(1)
            diesel_station_ids.add(int(diesel_station_id))
            address = link.parent.find_next_sibling().text
            normalized_address = "".join(
                address.replace(".", "").replace(",", "").lower().split()
            )
            diesel_station_addresses.add(normalized_address)
    logger.info(
        "Found {count} diesel stations on the Costco diesel page",
        count=len(diesel_station_addresses),
    )

    # Mark stations that appear in the diesel page
    marked_diesel_station_count = 0
    for url_obj in urls:
        next_address = url_obj["streetAddress"] + url_obj["city"] + url_obj["state"]
        normalized_next_address = "".join(next_address.replace(".", "").lower().split())
        normalized_next_address_full_zip_code = (
            normalized_next_address + url_obj["postalCode"]
        )
        normalized_next_address_partial_zip_code = (
            normalized_next_address_full_zip_code[:-5]
        )
        if (
            normalized_next_address_full_zip_code in diesel_station_addresses
            or normalized_next_address_partial_zip_code in diesel_station_addresses
            or int(station_id_from_url_regex.search(url_obj["url"]).group(1))
            in diesel_station_ids
        ):
            marked_diesel_station_count += 1
            url_obj["hasDiesel"] = True
        else:
            url_obj["hasDiesel"] = False

    logger.info(
        "Marked {count} stations as having diesel", count=marked_diesel_station_count
    )
    if marked_diesel_station_count != len(diesel_station_addresses):
        logger.warning(
            "Marked {count} stations as having diesel, but {diesel_station_count} diesel stations were found on the Costco diesel page",
            count=marked_diesel_station_count,
            diesel_station_count=len(diesel_station_addresses),
        )
    return urls


def get_and_write_all_gas_station_urls() -> list:
    # When the warehouse name isn't the same as the city name, use the alt format
    warehouse_url_format_string = "https://www.costco.com/warehouse-locations/{city}-{state_code}-{location_id}.html"
    # alt_warehouse_url_format_string = "https://www.costco.com/warehouse-locations/{name}-{city}-{state_code}-{location_id}.html"
    warehouse_list_url = "https://www.costco.com/WarehouseListByStateDisplayView"
    p_start = time.perf_counter()
    logger.debug(get_request_log_fmt_str, url=warehouse_list_url)
    # Must send User-Agent, else will hang
    resp = requests.get(warehouse_list_url, headers={"User-Agent": user_agent})
    logger.info(
        api_response_log_fmt_str, status_code=resp.status_code, url=warehouse_list_url
    )
    if resp.status_code != 200:
        logger.error(abort_due_to_bad_response_fmt_str)
        resp.raise_for_status()
    logger.info(read_html_log_fmt_str, url=warehouse_list_url)
    soup = BeautifulSoup(resp.text, "html5lib")
    logger.info("Done reading HTML response tree from {url}", url=warehouse_list_url)
    logger.info("Finding script tag with warehouse list...")
    # The JS script tag containing all of the warehouses as a list var should be at index 11
    js_script_tags = soup.find_all("script", attrs={"type": "text/javascript"})
    try:
        script_containing_warehouse_list_guess = js_script_tags[11]
        warehouse_list_as_str = script_containing_warehouse_list_guess.string.split(
            "=", 1
        )[1].rsplit(";", 1)[0]
    except IndexError as e:
        logger.error("Could not find the script tag with the warehouse list", e)
        raise AssertionError(
            "Targeted script tag does not contain the list of warehouses"
        )
    warehouse_list = json.loads(warehouse_list_as_str)
    logger.info("Found and loaded warehouse list.")
    gas_station_urls = []
    for state_with_warehouses in warehouse_list:
        state_code = state_with_warehouses["stateCode"].lower()
        for warehouse in state_with_warehouses["warehouseList"]:
            if warehouse["hasGasDepartment"]:
                location_name = warehouse["locationName"]
                # location_name_lower = location_name.lower()
                city_lower = warehouse["city"].lower()
                city = city_lower.title()
                location_id = warehouse["identifier"]
                url_to_write = warehouse_url_format_string.format(
                    city=city_lower,
                    state_code=state_code,
                    location_id=location_id,
                )
                # alt_url_to_write = alt_warehouse_url_format_string.format(
                #     name=location_name_lower,
                #     city=city_lower,
                #     state_code=state_code,
                #     location_id=location_id,
                # )
                gas_station_urls.append(
                    {
                        "name": location_name,
                        "streetAddress": warehouse["address1"].title(),
                        "city": city,
                        "state": warehouse["state"],
                        "postalCode": warehouse["zipCode"],
                        "latitude": warehouse["latitude"],
                        "longitude": warehouse["longitude"],
                        "url": url_to_write.replace(" ", "-"),
                        # "altUrl": alt_url_to_write.replace(" ", "-"),
                    }
                )
    p_end = time.perf_counter()
    logger.info(
        "Done writing all Costco US warehouse URLs with gas stations. Took {time_s} s",
        time_s=p_end - p_start,
    )
    # mark_diesel_station_urls(gas_station_urls)
    write_urls_to_file(gas_station_urls)
    return gas_station_urls


def get_and_normalize_data_from_url(url_object: dict) -> dict | None:
    franchise_name = "COSTCO"
    name = url_object["name"] + " (Costco)"
    street_address = url_object["streetAddress"]
    city = url_object["city"]
    state = url_object["state"]
    postal_code = url_object["postalCode"]
    latitude = url_object["latitude"]
    longitude = url_object["longitude"]
    regular_price = None
    mid_grade_price = None
    premium_price = None
    diesel_price = None
    url = url_object["url"]
    global _should_abort
    if _should_abort:
        logger.warning("Abort flag set, setting gas prices to None for {url}", url=url)
    else:
        p_start = time.perf_counter()
        logger.debug(get_request_log_fmt_str, url=url)
        # Must send User-Agent, else will hang
        resp = requests.get(url, headers={"User-Agent": user_agent})
        logger.info(api_response_log_fmt_str, status_code=resp.status_code, url=url)
        if resp.status_code != 200:
            logger.error(abort_due_to_bad_response_fmt_str)
            if resp.status_code == 403 or resp.status_code == 429 and not _should_abort:
                logger.error("Being rate limited or honeypotted. Setting abort flag.")
                _should_abort = True
        else:
            logger.info(read_html_log_fmt_str, url=url)
            soup = BeautifulSoup(resp.text, "html5lib")
            gas_price_section = soup.find("div", attrs={"class": "gas-price-section"})
            # Should never happen, but I don't want to delete this safeguard completely from code
            # if gas_price_section is None:
            #     logger.info(
            #         "URL {url} does not have a gas-price-section. Returning None", url=url
            #     )
            #     return None
            # Map to normalized schema
            for gas_price in gas_price_section.find_all("div"):
                grade = None
                price = None
                for meaningful_descendant in gas_price.find_all("span"):
                    if (
                        grade is None
                        and "gas-type"
                        in meaningful_descendant.get_attribute_list("class")
                    ):
                        grade = meaningful_descendant.text
                    else:
                        price = float(meaningful_descendant.text.replace("$", "")[0:4])
                        if state == "PR":
                            price = convert_price_per_liter_to_price_per_gallon(price)
                match grade:
                    case "Regular":
                        regular_price = {"timestamp": now_in_epoch_ms(), "price": price}
                    case "Premium":
                        premium_price = {"timestamp": now_in_epoch_ms(), "price": price}
                    case "Diesel":
                        diesel_price = {"timestamp": now_in_epoch_ms(), "price": price}
                    case _:
                        logger.warning(
                            '{url} has unknown gas grade "{grade_name}". Gas price is={gas_price}',
                            url=url,
                            grade_name=grade,
                            gas_price=price,
                        )
            if (
                regular_price is None
                and mid_grade_price is None
                and premium_price is None
                and diesel_price is None
            ):
                logger.warning(
                    'URL "{url}" has a gas prices section, but no gas prices were found.',
                    url=url,
                )
            elif regular_price is None:
                logger.error(
                    "Expected a price for regular octane at {url}, but got None! html is {html}",
                    url=url,
                    html=gas_price_section.contents,
                )
            p_end = time.perf_counter()
            logger.info(
                "Got prices from {url} in {time_s} s", url=url, time_s=p_end - p_start
            )
    return {
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


def main(args):
    urls = None
    if args.refresh_station_list:
        logger.info("Updating list of Costco gas station URLs")
        urls = get_and_write_all_gas_station_urls()
    if args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        if urls is None:
            logger.info(
                "Reading Costco URLs from {file_name}",
                file_name=costco_station_urls_file_name,
            )
            with open(costco_station_urls_file_name, "r") as urls_file:
                urls = json.loads(urls_file.read())
        logger.info(
            "Creating pool of size {pool_size} to get Costco prices",
            pool_size=args.cpu_pool_size,
        )
        with Pool(processes=args.cpu_pool_size) as p:
            p_start = time.perf_counter()
            data = p.map(get_and_normalize_data_from_url, urls)
            data_with_nulls_removed = [price for price in data if price is not None]
            p_end = time.perf_counter()
            logger.info(
                "Got prices for all Costcos in {time_s} s", time_s=p_end - p_start
            )
        with open(_prices_output_file_name, "w") as out_file:
            out_file.write(json.dumps(data_with_nulls_removed, indent=2))


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
