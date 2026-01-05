SHELL = /bin/bash -eux
ENVOY_VERSION := v1.36.0

IMAGE_TAG := any
export IMAGE_TAG

COMPOSE_BAKE := true
export COMPOSE_BAKE

clean:
	docker compose kill
	docker compose down
	docker compose rm -f

clean-local-files:
	rm -rf /var/tmp/sovereign_cache
	rm /tmp/sovereign_v2_data_store.db 2>/dev/null || true
	rm /tmp/sovereign_v2_queue.db 2>/dev/null || true

build:
	# Build containers
	IMAGE_TAG=$(ENVOY_VERSION) \
		docker compose build envoy sovereign mock

lint:
	uv run ruff check src
	uv run ruff format --check src
	uv run ty check src

format:
	uv run ruff format
	uv run ruff check --fix
	uv run ruff check --select I --fix

run:
	IMAGE_TAG=$(ENVOY_VERSION) \
		SOVEREIGN_WORKER_V2_ENABLED=0 \
		LOG_FORMAT="human" \
		docker compose up --wait --build \
		$(ENVOY_CTRLPLANE_DAEMON) \
		envoy sovereign mock aws

run-worker-v2:
	IMAGE_TAG=$(ENVOY_VERSION) \
		SOVEREIGN_WORKER_V2_ENABLED=1 \
		LOG_FORMAT="human" \
		docker compose up --wait --build \
		$(ENVOY_CTRLPLANE_DAEMON) \
		envoy sovereign mock aws

run-daemon:
	ENVOY_CTRLPLANE_DAEMON='-d' make run

run-daemon-worker-v2:
	ENVOY_CTRLPLANE_DAEMON='-d' make run-worker-v2

run-ctrl: clean
	docker compose up --wait --build $(ENVOY_CTRLPLANE_DAEMON) sovereign

acceptance:
	mkdir -p test-reports
	docker compose build tavern-acceptance
	docker compose run --rm tavern-acceptance

unit:
	mkdir -p test-reports
	docker compose build tavern-unit
	docker compose run --rm -e SOVEREIGN_CONFIG=file://test/config/config.yaml tavern-unit

install-deps:
	uv sync --all-extras

lock-deps:
	docker run -it -v .:/proj python:3.12 /proj/scripts/sync-uv.sh

release: check_version
	docker compose run \
		-e TWINE_USERNAME \
		-e TWINE_PASSWORD \
		publisher \
		uv publish --username ${TWINE_USERNAME} --password ${TWINE_PASSWORD}

test-envoy-version:
	mkdir -p logs
	IMAGE_TAG=$(ENVOY_VERSION) \
		PYTEST_MARK="`echo $(ENVOY_VERSION) | tr . _` or all" \
		make run-daemon acceptance

test-envoy-version-worker-v2:
	mkdir -p logs
	IMAGE_TAG=$(ENVOY_VERSION) \
		PYTEST_MARK="`echo $(ENVOY_VERSION) | tr . _` or all" \
		make run-daemon-worker-v2 acceptance

check_version:
	@package_version=$$(uv run python -c 'import importlib.metadata; print(importlib.metadata.version("sovereign"))'); \
	git_tag=$$(git describe --tags --exact-match 2>/dev/null || echo ""); \
	if [ "$$package_version" = "$$git_tag" ]; then \
		echo "Package version and Git tag match: $$package_version"; \
	else \
		echo "Package version ($$package_version) and Git tag ($$git_tag) do not match"; \
		exit 1; \
	fi

.PHONY: clean up test release
test: unit test-envoy-version clean
