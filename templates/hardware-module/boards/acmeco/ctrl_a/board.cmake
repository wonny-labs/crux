# SPDX-License-Identifier: Apache-2.0
#
# Debug and flash runners of the fictional board. A real board names the probe
# and part it was checked with. Nothing in Crux runs these.

board_runner_args(jlink "--device=MIMXRT1062xxx6A")
include(${ZEPHYR_BASE}/boards/common/jlink.board.cmake)
