#!/usr/bin/env bash

# run inside:
# docker run -it -v .:/proj ubuntu:20.04 bash

cd /proj
export DEBIAN_FRONTEND=noninteractive
ln -snf /usr/share/zoneinfo/UTC /etc/localtime
echo "UTC" > /etc/timezone
apt-get update && apt-get install -y build-essential autoconf automake libtool pkg-config python3-dev

curl -LsSf https://astral.sh/uv/install.sh | sh

export PATH="$HOME/.local/bin:$PATH"

uv python install 3.12
uv sync --python 3.12 --all-extras
