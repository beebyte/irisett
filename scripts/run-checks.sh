#!/bin/bash

mypy . --fast-parser --strict-optional --silent-imports
flake8 --ignore=E402,E501,F401 .
