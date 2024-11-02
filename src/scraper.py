import costco
from costco import costco_station_urls_file_name
from datetime import datetime
import helpers
from helpers import user_agent
import json
from loguru import logger
from multiprocessing import Pool
import os
import requests
import samsclub
from samsclub import samsclub_us_data_source_url
import shutil
import time


db_repo_url_ssh = "git@github.com:franklinmoy3/the-gas-app-db.git"
db_repo_clone_dir = "/tmp/the-gas-app-db"
prices_file_name = "prices.json"
current_prices_url = (
    "https://raw.githubusercontent.com/franklinmoy3/the-gas-app-db/latest/prices.json"
)
_mounted_deploy_key_file_name = "/etc/secrets/id_rsa"
_user_home_private_ssh_key_file_name = os.path.expanduser("~/.ssh/id_rsa")
_preserved_user_home_private_ssh_key_file_name = os.path.expanduser("~/.ssh/id_rsa.old")


def dispatcher(url_object: dict):
    match url_object["franchise_name"]:
        case "COSTCO":
            return costco.get_and_normalize_data_from_url(url_object["url"])
        case "SAMS_CLUB":
            return samsclub.get_and_normalize_data_from_url(url_object["url"])
        case _:
            raise ValueError(
                "Invalid franchise_name: {name}", name=url_object["franchise_name"]
            )


def merge_prices(curr_prices: list, new_prices: list):
    # Merge the prices. If the new price is None, retain the old price
    # The output of Pool.map() is ordered, so the sorting of the current and old prices are the same
    merged_prices = []
    for new_station_state in new_prices:
        # Only possible if we're tracking a brand new station
        if len(curr_prices) == 0:
            # Just add initial data on the new station
            merged_prices.append(new_station_state)
            continue
        curr_station_state = curr_prices.pop(0)
        merged_regular_price = curr_station_state["regularPrice"]
        merged_mid_grade_price = curr_station_state["midGradePrice"]
        merged_premium_price = curr_station_state["premiumPrice"]
        merged_diesel_price = curr_station_state["dieselPrice"]

        if new_station_state["regularPrice"] is not None:
            merged_regular_price = new_station_state["regularPrice"]
        if new_station_state["midGradePrice"] is not None:
            merged_mid_grade_price = new_station_state["midGradePrice"]
        if new_station_state["premiumPrice"] is not None:
            merged_premium_price = new_station_state["premiumPrice"]
        if new_station_state["dieselPrice"] is not None:
            merged_diesel_price = new_station_state["dieselPrice"]

        merged_prices.append(
            {
                **new_station_state,
                "regularPrice": merged_regular_price,
                "midGradePrice": merged_mid_grade_price,
                "premiumPrice": merged_premium_price,
                "dieselPrice": merged_diesel_price,
            }
        )
    return merged_prices


def main(args):
    refreshed_costco_urls = None
    if args.refresh_station_list:
        logger.info("Will refresh all station lists...")
        refreshed_costco_urls = costco.write_and_get_all_gas_station_urls()
    if args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        urls = []
        logger.debug("Collecting URLs to scrape")
        url_collect_start = time.perf_counter()
        urls.append({"franchise_name": "SAMS_CLUB", "url": samsclub_us_data_source_url})
        if refreshed_costco_urls is not None:
            costco_urls_formatted = [
                {"franchise_name": "COSTCO", "url": url}
                for url in refreshed_costco_urls
            ]
        else:
            with open(costco_station_urls_file_name, "r") as costco_urls_file:
                costco_urls = json.loads(costco_urls_file.read())
                costco_urls_formatted = [
                    {"franchise_name": "COSTCO", "url": url} for url in costco_urls
                ]
        urls += costco_urls_formatted
        url_collect_end = time.perf_counter()
        logger.info(
            "Collected URLs to scrape in {time_s} s",
            time_s=url_collect_end - url_collect_start,
        )
        logger.info(
            "Creating pool of size {pool_size} to get all prices",
            pool_size=args.cpu_pool_size,
        )
        with Pool(processes=args.cpu_pool_size) as p:
            p_start = time.perf_counter()
            prices_list = p.map(dispatcher, urls)
            prices_with_nulls_removed = [
                price for price in prices_list if price is not None
            ]
            p_end = time.perf_counter()
            logger.info(
                "Collected unflattened data in {time_s} s", time_s=p_end - p_start
            )
        # Flatten the list, but be wary that parts of the list is already flattened
        #   i.e. the prices list will be like [[price1, price2], price3, price4]
        logger.debug("Flattening prices list")
        flatten_start = time.perf_counter()
        prices_already_flattened = [
            price for price in prices_with_nulls_removed if not isinstance(price, list)
        ]
        prices_to_flattened = [
            inner_price
            for price in prices_with_nulls_removed
            for inner_price in price
            if isinstance(price, list)
        ]
        new_prices = prices_to_flattened + prices_already_flattened
        flatten_end = time.perf_counter()
        logger.info(
            "Flattened prices list in {time_s} s", time_s=flatten_end - flatten_start
        )
        logger.info(
            "Data collected and normalized in {time_s} s",
            time_s=flatten_end - url_collect_start,
        )
        if not args.no_write_to_file:
            if os.path.exists(prices_file_name):
                with open(prices_file_name, "r") as price_file:
                    curr_prices = json.loads(price_file.read())
                merged_prices = merge_prices(curr_prices, new_prices)
            else:
                merged_prices = new_prices
            merged_prices_as_json = json.dumps(merged_prices, indent=2)
            # Write merged pricing update
            logger.debug(
                "Writing pricing update to {prices_file_name}",
                prices_file_name=prices_file_name,
            )
            with open(prices_file_name, "w+") as price_file:
                price_file.write(merged_prices_as_json)
            logger.info(
                "Wrote pricing update to {prices_file_name}",
                prices_file_name=prices_file_name,
            )
        if not args.no_update_db:
            # Get and merge pricing
            curr_prices_resp = requests.get(
                current_prices_url, headers={"User-Agent": user_agent}
            )
            if curr_prices_resp.status_code == 200:
                curr_prices = json.loads(curr_prices_resp.text)
                merged_prices = merge_prices(curr_prices, new_prices)
            else:
                merged_prices = new_prices
            merged_prices_as_json = json.dumps(merged_prices, indent=2)
            # Publish update to DB in GitHub
            logger.info("Preparing to apply pricing update to DB...")
            orig_dir = os.curdir
            did_preserve_key = False
            if args.use_mounted_deploy_key:
                try:
                    logger.debug("Preserving user's existing id_rsa")
                    shutil.copyfile(
                        _user_home_private_ssh_key_file_name,
                        _preserved_user_home_private_ssh_key_file_name,
                    )
                    did_preserve_key = True
                    logger.info("Preserved user's existing id_rsa")
                except FileNotFoundError:
                    logger.info(
                        "Nothing to preserve as no default id_rsa private key was found in the user directory"
                    )
                logger.debug("Copying mounted SSH deploy key")
                with open(_mounted_deploy_key_file_name, "r") as secret_file:
                    mounted_deploy_key = secret_file.read()
                with open(
                    _user_home_private_ssh_key_file_name, "w+"
                ) as private_key_file:
                    private_key_file.write(mounted_deploy_key)
                # Don't forget that it's the octal representation
                os.chmod(_user_home_private_ssh_key_file_name, 0o600)
                logger.info("Copied mounted SSH deploy key")
            logger.info("Cloning database repo...")
            clone_start = time.perf_counter()
            if (
                os.system(
                    "git clone --depth=1 {db_repo} {target_dir}".format(
                        db_repo=db_repo_url_ssh, target_dir=db_repo_clone_dir
                    )
                )
                != 0
            ):
                raise RuntimeError(
                    "Failed to clone {db_repo} to location {target_dir}".format(
                        db_repo=db_repo_url_ssh, target_dir=db_repo_clone_dir
                    )
                )
            clone_end = time.perf_counter()
            logger.info(
                "Pricing DB repo cloned in {time_s} s", time_s=clone_end - clone_start
            )
            logger.info("Applying pricing update...")
            with open(
                os.path.join(db_repo_clone_dir, prices_file_name), "w+"
            ) as price_file:
                price_file.write(merged_prices_as_json)
            os.chdir(db_repo_clone_dir)
            logger.info("Staging pricing update...")
            os.system("git add {prices_file}".format(prices_file=prices_file_name))
            today = datetime.today().strftime("%Y-%m-%d")
            os.system('git commit -m "Pricing update: {today}"'.format(today=today))
            os.system(
                'git tag -a -f -m "Pricing update for {today}" {today}'.format(
                    today=today
                )
            )
            logger.info("Pricing update for {today} staged. Pushing...", today=today)
            push_start = time.perf_counter()
            if os.system("git push") != 0:
                logger.error("Failed to push pricing update")
                raise RuntimeError("Failed to push pricing update")
            # Force update the tag name
            if os.system("git push origin {today} --force".format(today=today)):
                logger.error("Failed to push tag for {today}", today=today)
            push_end = time.perf_counter()
            logger.info(
                "Pricing update pushed in {time_s} s. Cleaning up...",
                time_s=push_end - push_start,
            )
            shutil.rmtree(db_repo_clone_dir, ignore_errors=True)
            if did_preserve_key:
                logger.debug("Restoring with user's existing private SSH key")
                shutil.move(
                    _preserved_user_home_private_ssh_key_file_name,
                    _user_home_private_ssh_key_file_name,
                )
                logger.info("Restored user's existing private SSH key")
            os.chdir(orig_dir)
        scraper_end = time.perf_counter()
        logger.info(
            "Scraper finished in {time_s} s", time_s=scraper_end - url_collect_start
        )


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
