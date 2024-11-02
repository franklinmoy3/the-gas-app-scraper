# The Gas App Scraper <!-- omit in toc -->

A collection of scripts to scrape U.S. gas price data at select gas station brands.

- [Running the Scripts](#running-the-scripts)
  - [Install Dependencies](#install-dependencies)
  - [Run the Scripts](#run-the-scripts)
- [Cloud Deployment](#cloud-deployment)

## Running the Scripts

### Install Dependencies

This project uses `pipenv` to manage dependencies.
If you don't have it installed, you can install it with the following command:

```bash
pip install --user pipenv
```

Then, install the dependencies with the following command:

```bash
pipenv install
```

### Run the Scripts

The scripts are located in the [`src` directory](./src) and are written in Python.
They can be run with the Python interpreter. To see the usage information for each script, run:

```bash
python3 src/<script_name>.py --help
```

## Cloud Deployment

The scraper is currently deployed to GCP.

The CI/CD pipeline for the scraper is defined in the [cloudbuild.yaml file](./cloudbuild.yaml).
It is triggered by a pushed git tag that follows semantic versioning and ends in `-prod-release`. The trigger was created in the GCP Console.

The pipeline uses the [`Dockerfile`](./Dockerfile) to build the container image, which is then pushed to GCP Artifact Registry. The pipeline finally updates the Cloud Run Job with the new image.
