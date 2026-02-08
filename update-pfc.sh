#!/bin/bash
# PeeperFrog Create - Quick Update Script
# Run from anywhere: update-pfc
# (setup.py creates a symlink in ~/.local/bin/)

# Resolve symlink to get actual script location
SCRIPT_PATH="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT_PATH")" || exit 1

# Download any changes to setup.py
git fetch origin
git checkout origin/main -- setup.py

# Run setup.py
python3 setup.py "$@"
