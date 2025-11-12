FROM node:trixie-slim as node

WORKDIR /proj
ADD ./src/sovereign_files/static ./src/sovereign_files/static
ADD package.json package.json
ADD package-lock.json package-lock.json
RUN npm install
RUN npm run build-bulma

# ------------------------------------------------------------------------------------------------
FROM python:3.12 as python-base
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT=/opt/uv
ENV VIRTUAL_ENV=$UV_PROJECT_ENVIRONMENT
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# ------------------------------------------------------------------------------------------------
FROM python-base as dev

# ==== Install uv
ENV PIPX_HOME="/usr/local/pipx"
ENV PIPX_BIN_DIR="/usr/local/bin"
RUN pip install pipx && pipx install uv

# ==== Cache python dependencies here
WORKDIR /opt/app
COPY ./uv.lock ./pyproject.toml ./
RUN uv sync --no-dev --no-editable --no-install-project --locked --all-extras
ADD templates ./templates
ADD README.md ./README.md
ADD CHANGELOG.md ./CHANGELOG.md
ADD CODE_OF_CONDUCT.md ./CODE_OF_CONDUCT.md

# ------------------------------------------------------------------------------------------------
FROM dev as testing
# ==== Install development dependencies
RUN uv sync --no-install-project

ADD ./src ./src
COPY --from=node /proj/src/sovereign_files/static/style.css ./src/sovereign_files/static/style.css
COPY --from=node /proj/src/sovereign_files/static/style.css.map ./src/sovereign_files/static/style.css.map
RUN uv sync --all-extras
# ==== Add tests
COPY test ./test
COPY pytest.ini ./pytest.ini

# ------------------------------------------------------------------------------------------------
FROM dev as production

ADD ./src ./src
COPY --from=node /proj/src/sovereign_files/static/style.css ./src/sovereign_files/static/style.css
COPY --from=node /proj/src/sovereign_files/static/style.css.map ./src/sovereign_files/static/style.css.map
# Have to include test configs unfortunately
COPY test ./test
RUN uv sync --all-extras

EXPOSE 8080
CMD ["sovereign"]
