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

release:
	rm -rf dist
	python setup.py sdist bdist_egg
	twine upload dist/* --skip-existing


.PHONY: clean up test release
