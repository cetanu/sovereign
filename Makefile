SHELL = /bin/bash -eux
ENVOY_VERSION := v1.25.3
IMAGE_TAG := any
export IMAGE_TAG

clean:
	docker compose kill
	docker compose down
	docker compose rm -f

build:
	# Build containers
	IMAGE_TAG=$(ENVOY_VERSION) \
	docker compose build envoy sovereign mock

lint:
	poetry run ruff check src
	poetry run ruff format --check src
	poetry run mypy src

run:
	IMAGE_TAG=$(ENVOY_VERSION) \
	docker compose up --build \
		$(ENVOY_CTRLPLANE_DAEMON) \
		envoy sovereign mock redis

run-daemon:
	ENVOY_CTRLPLANE_DAEMON='-d' make run

run-ctrl: clean
	docker compose up --build $(ENVOY_CTRLPLANE_DAEMON) sovereign

acceptance:
	mkdir -p test-reports
	docker compose build tavern-acceptance
	docker compose run --rm tavern-acceptance

unit:
	mkdir -p test-reports
	docker compose build tavern-unit
	docker compose run --rm -e SOVEREIGN_CONFIG=file://test/config/config.yaml tavern-unit

install-deps:
	poetry install
	poetry install -E ujson -E orjson -E caching -E httptools
	poetry config cache-dir "~/.cache/pip"

release: check_version
	poetry build
	poetry publish -u $(TWINE_USERNAME) -p $(TWINE_PASSWORD)

test-envoy-version:
	mkdir -p logs
	IMAGE_TAG=$(ENVOY_VERSION) \
	PYTEST_MARK=`echo $(ENVOY_VERSION) | tr . _` \
	make run-daemon acceptance

check_version:
	@package_version=$$(poetry version | awk '{print $$2}'); \
	git_tag=$$(git describe --tags --exact-match 2>/dev/null || echo ""); \
	if [ "$$package_version" = "$$git_tag" ]; then \
		echo "Package version and Git tag match: $$package_version"; \
	else \
		echo "Package version ($$package_version) and Git tag ($$git_tag) do not match"; \
		exit 1; \
	fi

.PHONY: clean up test release
test: unit test-envoy-version clean
