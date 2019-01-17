SHELL = /bin/bash -eux

html:
	rm -rf src/sovereign/docs
	docker-compose build sphinx
	docker-compose run -e SOVEREIGN_CONFIG=file://test/config/config.yaml sphinx

clean:
	docker-compose kill
	docker-compose down
	docker-compose rm -f

run: clean
	# Validate compose config
	docker-compose config
	# Build containers
	docker-compose build envoy-control-plane
	docker-compose build envoy
	docker-compose build envoy-static
	# Run containers
	docker-compose up $(ENVOY_CTRLPLANE_DAEMON) envoy envoy-control-plane envoy-static

run-daemon:
	ENVOY_CTRLPLANE_DAEMON='-d' make run

run-ctrl: clean
	docker-compose up --build $(ENVOY_CTRLPLANE_DAEMON) envoy-control-plane

test: clean unit run-daemon acceptance clean

acceptance:
	docker-compose build tavern-acceptance
	docker-compose run tavern-acceptance

lint:
	pylint src/sovereign

unit:
	docker-compose build tavern-unit
	docker-compose run -e SOVEREIGN_CONFIG=file://test/config/config.yaml tavern-unit

release: html
	rm -rf dist
	python setup.py sdist bdist_egg
	twine upload dist/*


.PHONY: clean up test release
