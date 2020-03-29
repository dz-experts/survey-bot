SHELL := /bin/bash

all:

fixwindows:
	# If you are on Windows cmd or powershell, make sure you run these commands first
	# set COMPOSE_CONVERT_WINDOWS_PATHS=1
	# chcp 850

test:
	python -W ignore -m pytest -x --pdb

shell:
	docker-compose -f docker-compose.yml run --rm --service-ports app bash
