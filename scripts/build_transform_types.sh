#!/bin/sh

# Check quicktype is installed
if
  ! command -v quicktype &> /dev/null  
then
  echo "quicktype could not be found"
  echo "Please install it with 'npm install -g quicktype'"
  exit
fi

if
  ! command -v yq &> /dev/null  
then
  echo "yq could not be found"
  echo "Please install it with 'brew install yq'"
  exit
fi

INPUT=marimo/_plugins/ui/_impl/dataframes/transforms.yaml
PY_OUTPUT=marimo/_plugins/ui/_impl/dataframes/transforms.py
TS_OUTPUT=marimo/src/plugins/impl/dataframes/transforms.ts

yq e -o=json $INPUT | quicktype --src - --src-lang schema --out $PY_OUTPUT --just-types

# quicktype --src $INPUT --src-lang yml --out $PY_OUTPUT
