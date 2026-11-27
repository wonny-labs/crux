#include "crux_time_command.h"

#include <zephyr/shell/shell.h>

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#define COMMAND_CAPACITY 64
#define COMMAND_MAX_WORDS_AFTER_TIME 2

/* Joins `time` and argv[first..] into one line for the parser that the Linux Host shares. */
static int run_time_command(const struct shell *shell, size_t argc, char **argv, size_t first)
{
    char command[COMMAND_CAPACITY] = "time";
    size_t used = sizeof("time") - 1;

    if (argv == NULL || argc < first || argc - first > COMMAND_MAX_WORDS_AFTER_TIME) {
        shell_print(shell, "ERR INVALID_ARGUMENT");
        return 0;
    }

    for (size_t index = first; index < argc; ++index) {
        if (argv[index] == NULL) {
            shell_print(shell, "ERR INVALID_ARGUMENT");
            return 0;
        }

        const size_t token_size = strlen(argv[index]);
        if (token_size >= sizeof(command) - used - 1) {
            shell_print(shell, "ERR INVALID_ARGUMENT");
            return 0;
        }

        const int written = snprintf(command + used, sizeof(command) - used, " %s", argv[index]);
        if (written < 0 || (size_t)written >= sizeof(command) - used) {
            shell_print(shell, "ERR INVALID_ARGUMENT");
            return 0;
        }
        used += (size_t)written;
    }

    const crux_time_command_result_t response = crux_time_command_execute(command);
    if (response.kind == CRUX_TIME_COMMAND_HELP && response.status == CRUX_OK) {
        shell_print(shell, "%s", crux_time_command_help_text());
    } else if (response.status == CRUX_OK) {
        shell_print(shell, "%s", response.text);
    } else {
        shell_print(shell, "%s", crux_time_command_cli_error_text(response.status));
    }

    return 0;
}

/* `time` alone or followed by a word that is not a subcommand. */
static int time_command(const struct shell *shell, size_t argc, char **argv)
{
    if (argc == 0 || argv == NULL || argv[0] == NULL || strcmp(argv[0], "time") != 0) {
        shell_print(shell, "ERR INVALID_ARGUMENT");
        return 0;
    }
    return run_time_command(shell, argc, argv, 1);
}

/* argv[0] is the subcommand word (`get`, `help` or `set`). */
static int time_subcommand(const struct shell *shell, size_t argc, char **argv)
{
    return run_time_command(shell, argc, argv, 0);
}

/*
 * SHELL_CMD sets no argument count, so the shared parser checks the words: a wrong count answers
 * `ERR INVALID_ARGUMENT` with status 0, as on the Linux Host and in the board tests. A shell count
 * check would print "<command>: wrong parameter count" and return -EINVAL instead.
 */
SHELL_STATIC_SUBCMD_SET_CREATE(
    time_subcommands, SHELL_CMD(get, NULL, "Print the clock in UTC.", time_subcommand),
    SHELL_CMD(help, NULL, "List the Time commands.", time_subcommand),
    SHELL_CMD(set, NULL, "Set the clock from UTC: set YYYY-MM-DDTHH:MM:SS", time_subcommand),
    SHELL_SUBCMD_SET_END);

SHELL_CMD_ARG_REGISTER(time, &time_subcommands, "Crux UTC Time commands", time_command, 1,
                       SHELL_OPT_ARG_CHECK_SKIP);
