# Boards

Each board that Crux runs on has one page here. The page holds everything specific to that board: its `-b` target, switches and jumpers, probe and connection, flash and debug, recovery, board image profiles and known limits. [Getting started](../getting-started.md) and the [Tutorial](../tutorial.md#part-c-run-on-your-board) link these pages and hold no board procedure.

| Board | `-b` target | Board guide |
| --- | --- | --- |
| NXP MIMXRT1060-EVKB, revision B | `mimxrt1060_evk@B//qspi` | [MIMXRT1060-EVKB](mimxrt1060_evkb.md) |

Which components have evidence on each board is recorded in [Component readiness](../component-readiness.md).

## Adding a board

1. Bring the board up as [Porting Crux to a new board](../porting-to-a-new-board.md) describes.
2. Add `docs/boards/<board>.md` with the same sections as the existing page: Board target, Switches and jumpers, Probe and connection, Flash and debug, Recovery, Board image profiles and Known limits. Describe only procedures that have been run ([documentation guidelines](../documentation-guidelines.md#5-current-state-only)).
3. Add one row to the table above and one row to the board table in [Part C of the Tutorial](../tutorial.md#part-c-run-on-your-board).
4. Give the page its type (`how-to`) in [`tests/build/fixtures/docs_page_types.json`](../../tests/build/fixtures/docs_page_types.json).

A product repository built on Crux links these pages and keeps only its product-specific board steps ([documentation guidelines](../documentation-guidelines.md#6-onboarding-and-board-pages)).
