from bs4 import BeautifulSoup
import helpers
from helpers import (
    get_request_log_fmt_str,
    api_response_log_fmt_str,
    abort_due_to_bad_response_fmt_str,
    read_html_log_fmt_str,
    results_queue_type_error_msg,
)
import json
from loguru import logger
import multiprocessing as mp
from multiprocessing import Pool
from multiprocessing.queues import Queue
import requests
import time


gas_station_urls_file_name = "costco-gas-station-urls-us.json"


def write_and_get_all_gas_station_urls() -> list:
    # When the warehouse name isn't the same as the city name, use the alt format
    warehouse_url_format_string = (
        "https://costco.com/warehouse-locations/{city}-{state_code}-{location_id}.html"
    )
    alt_warehouse_url_format_string = "https://costco.com/warehouse-locations/{name}-{city}-{state_code}-{location_id}.html"
    warehouse_list_url = "https://www.costco.com/WarehouseListByStateDisplayView"
    p_start = time.perf_counter()
    logger.info(get_request_log_fmt_str, url=warehouse_list_url)
    # Must send User-Agent, else will hang
    resp = requests.get(
        warehouse_list_url, headers={"User-Agent": "PostmanRuntime/7.39.1"}
    )
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
    with open(gas_station_urls_file_name, "w") as out_file:
        logger.info(
            "Writing Costco US warehouse URLs that have gas stations to {file_name}",
            file_name=out_file.name,
        )
        gas_station_urls = []
        for state_with_warehouses in warehouse_list:
            state_code = state_with_warehouses["stateCode"].lower()
            for warehouse in state_with_warehouses["warehouseList"]:
                if warehouse["hasGasDepartment"]:
                    location_name = warehouse["locationName"].lower()
                    city = warehouse["city"].lower()
                    location_id = warehouse["identifier"]
                    if location_name == city:
                        url_to_write = warehouse_url_format_string.format(
                            city=city, state_code=state_code, location_id=location_id
                        )
                    else:
                        url_to_write = alt_warehouse_url_format_string.format(
                            name=location_name,
                            city=city,
                            state_code=state_code,
                            location_id=location_id,
                        )
                    gas_station_urls.append(url_to_write.replace(" ", "-"))
        out_file.write(json.dumps(gas_station_urls, indent=2))
    p_end = time.perf_counter()
    logger.info(
        "Done writing all Costco US warehouse URLs with gas stations. Took {time_s} s",
        time_s=p_end - p_start,
    )
    return gas_station_urls


def get_and_normalize_data_for_station(url: str) -> dict | None:
    # Must send User-Agent, else will hang
    logger.info(get_request_log_fmt_str, url=url)
    resp = requests.get(url, headers={"User-Agent": "PostmanRuntime/7.39.1"})
    logger.info(api_response_log_fmt_str, status_code=resp.status_code, url=url)
    if resp.status_code != 200:
        logger.error(abort_due_to_bad_response_fmt_str)
        resp.raise_for_status()
    logger.info(read_html_log_fmt_str, url=url)
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
    elif regular_price == None:
        logger.error(
            "Expected a price for regular octane at {url}, but got None!", url=url
        )
    return {
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


def get_and_normalize_data_from_source(urls: list, cpu_pool_size: int) -> list:
    logger.info(
        "Creating multiprocessing pool of size {process_count} to gather Costco gas prices",
        process_count=cpu_pool_size,
    )
    with Pool(cpu_pool_size) as p:
        p_start = time.perf_counter()
        data = p.map(get_and_normalize_data_for_station, urls)
        p_end = time.perf_counter()
        logger.info("Data collection took {time_s} s", time_s=p_end - p_start)
    return data


def collect_data(cpu_pool_size: int, **kwargs) -> list:
    results_queue_present = False
    if "results_queue" in kwargs:
        if isinstance(kwargs["results_queue"], Queue):
            results_queue_present = True
        else:
            raise TypeError(results_queue_type_error_msg)
    with open(gas_station_urls_file_name, "r") as file:
        urls = json.loads(file.read())
    data = get_and_normalize_data_from_source(urls, cpu_pool_size)
    logger.info(
        "Collected prices on {len_urls} Costco gas stations", len_urls=len(urls)
    )
    if results_queue_present:
        kwargs["results_queue"].put(obj=data)
        kwargs["results_queue"].close()
    return data


def main(run_args):
    if args.refresh_station_list:
        logger.info(
            'Will refresh station list as "--refresh-station-list" was specified'
        )
        write_and_get_all_gas_station_urls()
    if args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        data = collect_data(cpu_pool_size=run_args.cpu_pool_size)
        with open("costco-prices-out.json", "w") as out_file:
            out_file.write(json.dumps(data, indent=2))


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)