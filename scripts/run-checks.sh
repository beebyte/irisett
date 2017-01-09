#!/bin/bash

mypy . --fast-parser --strict-optional --ignore-missing-imports --disallow-untyped-defs --disallow-untyped-calls
flake8 --ignore=E402,E501,F401 .
