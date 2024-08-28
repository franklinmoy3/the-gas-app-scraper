REPO_ROOT := $(shell git rev-parse --show-toplevel)

.DEFAULT_GOAL: init

.PHONY: init requirements chromedriver

init:
	pip install -r $(REPO_ROOT)/requirements.txt

requirements:
	pip freeze > $(REPO_ROOT)/requirements.txt
