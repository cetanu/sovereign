# ------------------------------------------------------------------------------------------------
FROM python:3.11 as python-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"
# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


# ------------------------------------------------------------------------------------------------
FROM python-base as dev

# ==== Install poetry
ENV PIPX_HOME="/usr/local/pipx"
ENV PIPX_BIN_DIR="/usr/local/bin"
RUN pip install pipx~=1.1.0
RUN pipx install poetry~=1.2.2

# ==== Cache python dependencies here
WORKDIR $PYSETUP_PATH
COPY ./poetry.lock ./pyproject.toml ./
RUN poetry install --only main --no-root --extras "boto orjson statsd sentry caching"
ADD templates ./templates
ADD README.md ./README.md
ADD CHANGELOG.md ./CHANGELOG.md
ADD CODE_OF_CONDUCT.md ./CODE_OF_CONDUCT.md

# ------------------------------------------------------------------------------------------------
FROM dev as testing
# ==== Install development dependencies
RUN poetry install --no-root

ADD ./src ./src
RUN poetry install
RUN poetry install -E ujson -E orjson -E caching
# ==== Add tests
COPY test ./test
COPY pytest.ini ./pytest.ini

# ------------------------------------------------------------------------------------------------
FROM dev as production

ADD ./src ./src
# Have to include test configs unfortunately
COPY test ./test
RUN poetry install --only main -E caching

EXPOSE 8080
CMD sovereign
