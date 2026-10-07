#!/usr/bin/env bash
# Starts the server. Uses the virtual environment in ./venv when it exists.
cd "$(dirname "$0")"
if [ -x venv/bin/python ]; then venv/bin/python app.py; else python3 app.py; fi
