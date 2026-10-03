#!/bin/bash
# Usage: run.sh <checkout> <probe files...> [-- pytest args]. Copies the probes into
# <checkout>/engine/tests/web/r2probe/ (untracked) and runs them there, keys stripped.
WT=$1; shift
PD=$WT/engine/tests/web/r2probe
mkdir -p $PD; touch $PD/__init__.py
files=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do cp "$1" $PD/; files+=("tests/web/r2probe/$(basename $1)"); shift; done
[ "$1" = "--" ] && shift
cd $WT/engine || exit 1
exec /tmp/claude-0/-home-user-shitpost-alpha/aa37c4ca-915a-53be-b149-d37cd9089ba3/scratchpad/clean.sh PYTHONPATH=$WT/engine timeout 1500 /home/user/engine-venv-262/bin/python -m pytest -p no:cacheprovider "${files[@]}" "$@"
