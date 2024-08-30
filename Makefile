REPO_ROOT := $(shell git rev-parse --show-toplevel)

.DEFAULT_GOAL: init

.PHONY: init requirements chromedriver

init:
	pipenv install
