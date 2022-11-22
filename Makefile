SHELL = /bin/bash -eux
IMAGE_TAG := any
export IMAGE_TAG

clean:
	docker-compose kill
	docker-compose down
	docker-compose rm -f

build:
	# Build containers
	IMAGE_TAG=$(ENVOY_VERSION) \
	docker-compose build envoy envoy-control-plane

run: build
	IMAGE_TAG=$(ENVOY_VERSION) \
	docker-compose up \
		$(ENVOY_CTRLPLANE_DAEMON) \
		envoy envoy-control-plane

run-daemon:
	ENVOY_CTRLPLANE_DAEMON='-d' make run

run-ctrl: clean
	docker-compose up --build $(ENVOY_CTRLPLANE_DAEMON) envoy-control-plane

acceptance:
	docker-compose build tavern-acceptance
	docker-compose run tavern-acceptance

unit:
	docker-compose build tavern-unit
	docker-compose run -e SOVEREIGN_CONFIG=file://test/config/config.yaml tavern-unit

install-deps:
	curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python
	poetry install
	poetry install -E ujson -E orjson
	poetry config cache-dir "~/.cache/pip"

release:
	poetry build
	poetry publish -u $(TWINE_USERNAME) -p $(TWINE_PASSWORD)

test-envoy-version:
	IMAGE_TAG=$(ENVOY_VERSION) \
	PYTEST_MARK=`echo $(ENVOY_VERSION) | tr . _` \
	make run-daemon acceptance

.PHONY: clean up test release
test: unit test-envoy-version clean
