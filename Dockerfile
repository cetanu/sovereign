# ------------------------------------------------------------------------------------------------
FROM python:3.8 as python-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.0.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"
# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"


# ------------------------------------------------------------------------------------------------
FROM python-base as dev

# ==== Install poetry
ENV POETRY_VERSION=1.0.5
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python

# ==== Cache python dependencies here
WORKDIR $PYSETUP_PATH
COPY ./poetry.lock ./pyproject.toml ./
RUN poetry install --no-dev --no-root --extras "boto orjson statsd sentry"
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
# ==== Add tests
COPY test ./test
COPY pytest.ini ./pytest.ini

# ------------------------------------------------------------------------------------------------
FROM dev as production

ADD ./src ./src
# Have to include test configs unfortunately
COPY test ./test
RUN poetry install --no-dev

EXPOSE 8080
CMD sovereign
