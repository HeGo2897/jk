#!/usr/bin/env bash
# One-time setup: creates ./venv and installs Flask (add --mysql to also install the MySQL driver).
set -e
cd "$(dirname "$0")"
python3 -m venv venv
FILE=requirements.txt
[ "$1" = "--mysql" ] && FILE=requirements-mysql.txt
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r "$FILE"
echo "Setup OK. Start the server with ./run.sh"
