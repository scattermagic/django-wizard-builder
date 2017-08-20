VERSION := $(shell cat wizard_builder/version.txt)

help:
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

clean-lint: ## run the cleanup functions for the linters
	autopep8 wizard_builder/ -raai
	isort -rc wizard_builder/
	make test-lint

test-lint: ## lint with isort and flake8
	flake8 wizard_builder/
	isort --check-only --diff --quiet -rc wizard_builder/

test-fast:
	pytest -vlsx --ff --reuse-db

test-local-suite:
	python manage.py check
	pytest -v

test-callisto-core:
	pip install callisto-core --upgrade
	pip show callisto-core |\
		grep 'Location' |\
		sed 's/Location: \(.*\)/\1\/callisto_core\/requirements\/dev.txt/' |\
		xargs -t pip install --upgrade -r
	pip uninstall -y django-wizard-builder
	pip install -e .
	pip show callisto-core |\
		grep 'Location' |\
		sed 's/Location: \(.*\)/\1\/callisto_core\/tests/' |\
		xargs -t pytest -v --ds=wizard_builder.tests.test_callisto_core_settings

test-code:
	make test-local-suite
	make test-callisto-core

clean-build: ## clean the repo in preparation for release
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -rf wizard_builder/tests/screendumps/
	rm -rf wizard_builder/tests/staticfiles/
	find wizard_builder -name '*.pyc' -exec rm -f {} +
	find wizard_builder -name '*.pyo' -exec rm -f {} +
	find wizard_builder -name '*~' -exec rm -f {} +
	find wizard_builder -type d -name "__pycache__" -exec rm -rf {} +

release: ## package and upload a release
	make clean-build
	python setup.py sdist upload
	python setup.py bdist_wheel upload
	git tag -a $(VERSION) -m 'version $(VERSION)'
	git push --tags
	git push

app-setup: ## setup the test application environment
	python manage.py flush --noinput
	python manage.py migrate --noinput --database default
	python manage.py create_admins
	python manage.py setup_sites
	make load-fixture

shell: ## manage.py shell_plus with dev settings
	DJANGO_SETTINGS_MODULE='wizard_builder.tests.test_app.dev_settings' python manage.py shell_plus

load-fixture: ## load fixture from file
	python manage.py loaddata $(DATA_FILE)

create-fixture: ## create fixture from db
	python manage.py dumpdata wizard_builder -o $(DATA_FILE)
	npx json -f $(DATA_FILE) -I
