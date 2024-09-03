REPO_ROOT := $(shell git rev-parse --show-toplevel)

.DEFAULT_GOAL: init

.PHONY: init lint deptree fmt format

init:
	python3 -m pipenv install

lint:
	python3 -m flake8 -v

deptree:
	python3 -m pipdeptree -fl

format:
	python3 -m black .

fmt: format

