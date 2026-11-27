#!/usr/bin/env bash
# Alias of test-integration-probe-rt1170.sh under the name used downstream.
exec "$(dirname "${BASH_SOURCE[0]}")/test-integration-probe-rt1170.sh" "$@"
