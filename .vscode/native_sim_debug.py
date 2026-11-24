# SPDX-License-Identifier: Apache-2.0
"""gdb setup for the VS Code profile native_sim: Debug, sourced from its setupCommands.

When gdb loads zephyr.exe, this script:
- passes -uart_stdinout only if `zephyr.exe -h` lists it. Builds with a PTY UART (console or
  shell samples) accept it and then take shell input in the terminal; other builds reject it.
- sets a temporary breakpoint at the application main. zephyr.exe has two functions named main:
  the application's, and the native simulator runner's in
  zephyr/scripts/native_simulator/common/src/main.c, which runs first. A plain `tbreak main`
  would stop in the runner and delete itself.
"""
import subprocess

import gdb

RUNNER_DIR = "/native_simulator/"


def lists_uart_stdinout(program):
    result = subprocess.run([program, "-h"], capture_output=True, text=True, timeout=10, check=False)
    return "-uart_stdinout" in result.stdout + result.stderr


def application_main_source():
    # decode_line returns every location of an ambiguous linespec such as "main".
    _, locations = gdb.decode_line("main")
    for location in locations or ():
        if location.symtab is not None and RUNNER_DIR not in location.symtab.fullname():
            return location.symtab.fullname()
    return None


def set_up(program):
    if lists_uart_stdinout(program):
        gdb.execute("set args -uart_stdinout")
    source = application_main_source()
    if source is None:
        gdb.write("native_sim_debug.py: no application main found; no breakpoint set\n")
        return
    gdb.Breakpoint(source=source, function="main", temporary=True)


def on_new_objfile(event):
    program = gdb.current_progspace().filename
    if program is None or event.new_objfile.filename != program:
        return  # a shared library, not zephyr.exe
    gdb.events.new_objfile.disconnect(on_new_objfile)
    try:
        set_up(program)
    except (gdb.error, OSError, subprocess.SubprocessError) as error:
        gdb.write(f"native_sim_debug.py: {error}\n")


# The C/C++ extension runs setupCommands before it loads the program, so wait for it.
if gdb.current_progspace().filename is None:
    gdb.events.new_objfile.connect(on_new_objfile)
else:
    set_up(gdb.current_progspace().filename)
