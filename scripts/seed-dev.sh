#!/bin/sh
set -eu
# Phase 2+ will load Reddit fixtures via manage.py seed_dev_reddit.
echo "No Phase 1 seed data. Bootstrap an owner via POST /api/v1/auth/bootstrap/ or the login UI."
