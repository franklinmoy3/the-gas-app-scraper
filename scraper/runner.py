from costco import collect_data as get_costco_data
from datetime import datetime
import helpers
import json
from loguru import logger
from multiprocessing import Queue, Process
import os
from samsclub import collect_data as get_sams_data
import shutil
import time


started_scraper_process_fmt_str = "Started {franchise_name} subprocess"
db_repo_url = "git@github.com:franklinmoy3/the-gas-app-db.git"
db_repo_clone_dir = "/tmp/the-gas-app-db"
db_repo_prices_file_name = "prices.json"


def get_all_prices(cpu_pool_size: int) -> list:
    results = Queue()
    p_sams = Process(target=get_sams_data, kwargs={"results_queue": results})
    p_costco = Process(
        target=get_costco_data,
        kwargs={"results_queue": results, "cpu_pool_size": cpu_pool_size},
    )
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


def main(run_args):
    if run_args.no_collect_prices:
        logger.info('Will not collect prices as "--no-collect-prices" was specified')
    else:
        prices = get_all_prices(run_args.cpu_pool_size)
        data = {"timestamp": int(time.time() * 1000), "prices": prices}
        data_as_json = json.dumps(data, indent=2)
        # Publish update to DB in GitHub
        orig_dir = os.curdir
        logger.info("Cloning database repo...")
        os.system(
            "git clone --depth=1 {db_repo} {target_dir}".format(
                db_repo=db_repo_url, target_dir=db_repo_clone_dir
            )
        )
        logger.info("Applying pricing update...")
        with open(
            os.path.join(db_repo_clone_dir, db_repo_prices_file_name), "w+"
        ) as price_file:
            price_file.write(data_as_json)
        os.chdir(db_repo_clone_dir)
        logger.info("Staging pricing update...")
        os.system("git add {prices_file}".format(prices_file=db_repo_prices_file_name))
        today = datetime.today().strftime("%Y-%m-%d")
        os.system('git commit -m "Pricing update: {today}"'.format(today=today))
        os.system('git tag -f -a -m "Pricing update for {today}" {today}'.format(today=today))
        logger.info("Pricing update for {today} staged. Pushing...", today=today)
        os.system("git push --follow-tags --force")
        logger.info("Pricing update pushed! Cleaning up...")
        shutil.rmtree(db_repo_clone_dir, ignore_errors=True)
        os.chdir(orig_dir)


if __name__ == "__main__":
    args = helpers.parse_command_args()
    helpers.configure_logger(args)
    main(args)
