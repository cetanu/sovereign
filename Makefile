SHELL = /bin/bash -eux

html:
	rm -rf src/sovereign/docs
	docker-compose build sphinx
	docker-compose run -e SOVEREIGN_CONFIG=file://test/config/config.yaml sphinx

clean:
	docker-compose kill
	docker-compose down
	docker-compose rm -f

config:
	# Validate compose config
	docker-compose config

build:
	# Build containers
	docker-compose build envoy-control-plane
	docker-compose build envoy

run: config build clean
	# Run containers
	docker-compose up $(ENVOY_CTRLPLANE_DAEMON) envoy envoy-control-plane

run-daemon:
	ENVOY_CTRLPLANE_DAEMON='-d' make run

run-ctrl: clean
	docker-compose up --build $(ENVOY_CTRLPLANE_DAEMON) envoy-control-plane

test: unit run-daemon acceptance clean

acceptance:
	docker-compose build tavern-acceptance
	docker-compose run tavern-acceptance

lint:
	pylint src/sovereign

unit:
	docker-compose build tavern-unit
	docker-compose run -e SOVEREIGN_CONFIG=file://test/config/config.yaml tavern-unit

unit-local: echo-test-vars
	pytest -vv --tb=short --ignore=test/acceptance --junitxml=test-reports/unit.xml --cov=./src/sovereign

install-pkg:
	python setup.py sdist
	pip install dist/sovereign-*.tar.gz

install-deps:
	pip install --no-cache-dir --upgrade pip
	pip install --no-cache-dir --upgrade -r requirements-dev.txt

install: install-deps install-pkg

download-cc-reporter:
	curl -L https://codeclimate.com/downloads/test-reporter/test-reporter-latest-linux-amd64 > ./cc-test-reporter
	chmod +x cc-test-reporter

export-test-vars:
	export CONFIG_LOADER_TEST='{"hello": "world"}'
	export SOVEREIGN_ENVIRONMENT_TYPE=local
	export SOVEREIGN_CONFIG=file://test/config/config.yaml
	export GIT_COMMIT_SHA=${BITBUCKET_COMMIT}
	export GIT_BRANCH=${BITBUCKET_BRANCH}

echo-test-vars:
	echo CONFIG_LOADER_TEST='{"hello": "world"}'
	echo SOVEREIGN_ENVIRONMENT_TYPE=local
	echo SOVEREIGN_CONFIG=file://test/config/config.yaml
	echo GIT_COMMIT_SHA=${BITBUCKET_COMMIT}
	echo GIT_BRANCH=${BITBUCKET_BRANCH}

release:
	rm -rf dist
	python setup.py sdist bdist_egg
	twine upload dist/* --skip-existing


.PHONY: clean up test release
