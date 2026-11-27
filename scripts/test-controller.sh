#!/usr/bin/env bash
# Alias kept until the CI workflows call scripts/test-time-periodic.sh (held workflow change); then it is deleted.
exec "$(dirname "${BASH_SOURCE[0]}")/test-time-periodic.sh" "$@"
