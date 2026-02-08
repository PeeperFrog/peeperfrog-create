#!/bin/bash
# PeeperFrog Create - Quick Update Script
# Run from anywhere: update-pfc
# (setup.py creates a symlink in ~/.local/bin/)

cd "$(dirname "$0")" || exit 1

# Download any changes to setup.py
git fetch origin
git checkout origin/main -- setup.py

# Run setup.py
python3 setup.py "$@"
