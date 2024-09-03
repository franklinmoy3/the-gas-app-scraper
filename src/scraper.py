import costco
from costco import costco_station_urls_file_name
from datetime import datetime
import helpers
import json
from loguru import logger
from multiprocessing import Pool
import os
import samsclub
from samsclub import samsclub_us_data_source_url
import shutil
import time


db_repo_url = "git@github.com:franklinmoy3/the-gas-app-db.git"
db_repo_clone_dir = "/tmp/the-gas-app-db"
prices_file_name = "prices.json"


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


def main(args):
    if args.refresh_station_list:
        logger.info("Will refresh all station lists...")
    if args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        urls = []
        logger.debug("Collecting URLs to scrape")
        url_collect_start = time.perf_counter()
        urls.append({"franchise_name": "SAMS_CLUB", "url": samsclub_us_data_source_url})
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
            p_end = time.perf_counter()
            logger.info("Collected unflattened data in {time_s} s", time_s=p_end - p_start)
        # Flatten the list, but be wary that parts of the list is already flattened
        #   i.e. the prices list will be like [[price1, price2], price3, price4]
        logger.debug("Flattening prices list")
        flatten_start = time.perf_counter()
        prices = [price if not isinstance(price, list) else inner_price for price in prices_list for inner_price in price]
        data = {"timestamp": int(time.time() * 1000), "prices": prices}
        data_as_json = json.dumps(data, indent=2)
        flatten_end = time.perf_counter()
        logger.info("Flattened prices list in {time_s} s", time_s=flatten_end - flatten_start)
        logger.info("Data collected and normalized in {time_s} s", time_s=flatten_end - url_collect_start)
        if not args.no_write_to_file:
            logger.debug("Writing pricing update to {prices_file_name}", prices_file_name=prices_file_name)
            with open(prices_file_name, "w+") as price_file:
                price_file.write(data_as_json)
            logger.info("Wrote pricing update to {prices_file_name}", prices_file_name=prices_file_name)
        if not args.no_update_db:
            # Publish update to DB in GitHub
            logger.info("Preparing to apply pricing update to DB...")
            orig_dir = os.curdir
            logger.info("Cloning database repo...")
            clone_start = time.perf_counter()
            os.system(
                "git clone --depth=1 {db_repo} {target_dir}".format(
                    db_repo=db_repo_url, target_dir=db_repo_clone_dir
                )
            )
            clone_end = time.perf_counter()
            logger.info("Pricing DB repo cloned in {time_s} s", time_s=clone_end - clone_start)
            logger.info("Applying pricing update...")
            with open(
                os.path.join(db_repo_clone_dir, prices_file_name), "w+"
            ) as price_file:
                price_file.write(data_as_json)
            os.chdir(db_repo_clone_dir)
            logger.info("Staging pricing update...")
            os.system("git add {prices_file}".format(prices_file=prices_file_name))
            today = datetime.today().strftime("%Y-%m-%d")
            os.system('git commit -m "Pricing update: {today}"'.format(today=today))
            os.system(
                'git tag -f -a -m "Pricing update for {today}" {today}'.format(
                    today=today
                )
            )
            logger.info("Pricing update for {today} staged. Pushing...", today=today)
            push_start = time.perf_counter()
            os.system("git push --follow-tags --force")
            push_end = time.perf_counter()
            logger.info("Pricing update pushed in {time_s} s. Cleaning up...", time_s=push_end - push_start)
            shutil.rmtree(db_repo_clone_dir, ignore_errors=True)
            os.chdir(orig_dir)
        scraper_end = time.perf_counter()
        logger.info("Scraper finished in {time_s} s", time_s=scraper_end - url_collect_start)


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
