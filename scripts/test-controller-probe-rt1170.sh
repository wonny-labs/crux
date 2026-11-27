#!/usr/bin/env bash
# Alias of the old name of the runner.
exec "$(dirname "${BASH_SOURCE[0]}")/test-integration-probe-rt1170.sh" "$@"
