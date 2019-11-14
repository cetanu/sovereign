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

unit-local:
	CONFIG_LOADER_TEST='{"hello": "world"}' \
	SOVEREIGN_ENABLE_ACCESS_LOGS='False' \
	SOVEREIGN_ENVIRONMENT_TYPE=local \
	SOVEREIGN_CONFIG=file://test/config/config.yaml \
	coverage run --source=sovereign -m pytest -vv --tb=short -ra --ignore=test/acceptance --junitxml=test-reports/unit.xml --spec
	coverage report --show-missing

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

before-build: download-cc-reporter install
	GIT_COMMIT_SHA=${BITBUCKET_COMMIT} \
	GIT_BRANCH=${BITBUCKET_BRANCH} \
	./cc-test-reporter before-build

after-build:
	coverage xml
	mv src/sovereign sovereign
	./cc-test-reporter format-coverage --input-type coverage.py --prefix /usr/local/lib/python3.7/site-packages
	GIT_COMMIT_SHA=${BITBUCKET_COMMIT} \
	GIT_BRANCH=${BITBUCKET_BRANCH} \
	./cc-test-reporter upload-coverage
	exit ${BITBUCKET_EXIT_CODE}

release:
	rm -rf dist
	python setup.py sdist bdist_egg
	twine upload dist/* --skip-existing


test-envoy-version:
	IMAGE_TAG=$(ENVOY_VERSION) \
	PYTEST_MARK=`echo $(ENVOY_VERSION) | tr . _` \
	make run-daemon acceptance


.PHONY: clean up test release
