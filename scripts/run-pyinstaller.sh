#!/bin/bash

pyinstaller scripts/irisett -n irisett --onefile --add-data 'irisett/webmgmt/static/style.css:irisett/webmgmt/static/' --add-data 'irisett/webmgmt/templates/*:irisett/webmgmt/templates/'
