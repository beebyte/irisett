#!/bin/bash

mypy . --strict-optional --ignore-missing-imports --disallow-untyped-defs --disallow-untyped-calls --check-untyped-defs --warn-redundant-casts --warn-unused-ignores
flake8 --ignore=E402,E501,F401 .
