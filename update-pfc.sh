#!/bin/bash
# PeeperFrog Create - Quick Update Script
# Run from anywhere: update-pfc
# (setup.py creates a symlink in ~/.local/bin/)

cd "$(dirname "$0")" || exit 1
python3 setup.py "$@"
