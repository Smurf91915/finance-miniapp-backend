#!/bin/sh
set -eu

python3 -m pip install -e .
exec python3 -m app.bot.main
