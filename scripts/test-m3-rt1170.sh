#!/usr/bin/env bash
# Alias kept until the held workflow change; then it is deleted.
exec "$(dirname "${BASH_SOURCE[0]}")/test-integration-probe-rt1170.sh" "$@"
