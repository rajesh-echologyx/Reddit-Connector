#!/bin/sh
set -eu
cd "$(dirname "$0")/../backend"
export DJANGO_ENV="${DJANGO_ENV:-local}"
export REDDIT_MODE="${REDDIT_MODE:-fixture}"
python manage.py seed_dev_reddit --poll
