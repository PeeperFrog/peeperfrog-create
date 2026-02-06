#!/bin/bash
# PeeperFrog Create - Quick Update Script
# Run from anywhere: ~/peeperfrog-create/update-pfc.sh
# Or add to PATH and just run: update-pfc.sh

cd "$(dirname "$0")" || exit 1
python3 setup.py "$@"
