# Bash Tab completion for west. The Dockerfile installs this file in the bash-completion
# directory, and bash-completion sources it on the first `west <Tab>` in a shell.
#
# The completion script comes from `west completion bash`, a Zephyr extension command that
# exists only inside a west workspace (in the Dev Container, any folder under /workspace once
# scripts/bootstrap.sh has set it up). This file therefore asks west for the script at that
# moment instead of at image build time. Outside a workspace it defines nothing and prints
# nothing, so `west <Tab>` falls back to bash-completion's default.
if __crux_west_completion=$(west completion bash 2>/dev/null) && [ -n "$__crux_west_completion" ]; then
    eval "$__crux_west_completion"
fi
unset __crux_west_completion
