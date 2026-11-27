#!/usr/bin/env bash
# Alias of test-controller-integration.sh under the name used downstream.
exec "$(dirname "${BASH_SOURCE[0]}")/test-controller-integration.sh" "$@"
