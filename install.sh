#!/bin/sh
set -eu
CRD_SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$CRD_SOURCE_DIR/install.py" "$@"
