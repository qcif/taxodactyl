#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/../../.."

./deployment/azure/run-taxodactyl.sh --metadata test/selenium/inputs/metadata.csv
