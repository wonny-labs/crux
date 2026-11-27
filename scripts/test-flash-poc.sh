#!/usr/bin/env bash
# Alias kept until PR 10 of the samples layout plan; the maintained runner is renamed.
exec "$(dirname "${BASH_SOURCE[0]}")/test-flash-safety-check.sh" "$@"
