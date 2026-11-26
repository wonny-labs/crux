# LittleFS power-cut evidence plan

Status: **model part built; board part proposed and not approved.** No step of the board part may start without an approval that names the board, the card, the images, the flashing and the power rig.
Dated 26 November 2026.

This plan is for the owner and for whoever runs the campaign.
It says what evidence a product needs before it relies on [File on LittleFS](../file-contract.md#littlefs-block-device-mapping) and on [Configuration](../configuration-contract.md) saving on the same SD card or eMMC volume across power cuts.

## What LittleFS promises, and what it assumes

Upstream, the [littlefs README](https://github.com/littlefs-project/littlefs) states that remove and rename are atomic across power loss, and that the file system falls back to the last good state. A file's data and size are committed at a sync or a close.
These promises assume that the disk keeps what a sync acknowledged, in order.
A card or an eMMC device maps blocks itself, and its behaviour at a power cut is outside the promise. Only a run on the product's medium shows it.

## Model evidence

`scripts/test-storage-simulators.sh` runs the replay of `tests/native/emmc_powercut` on the eMMC simulator, with the MMC cache flush correction, with and without a device cache.
The cached profile runs the models `lost`, `prefix`, `reordered` and `torn`; the no-cache profile runs only `prefix` and `torn`.

| Workload | What it does | What every cut must keep |
| --- | --- | --- |
| W4 | Saves three keys through the Settings File backend | Mounts without a format; the settings file exists and each key is a complete value not older than acknowledged |
| W5 | Appends records through File: open, size, seek, write, sync, close | Every acknowledged record, complete and in order |
| W8 | Writes a temporary through File and renames it onto the target with the VFS rename | The target is one complete generation, not older than acknowledged |
| W8C | Replaces as File allows: remove the target, then rename | The window with no target is expected, and must appear in every generation |

Every cut must also leave an untouched file byte-exact and take a new write, sync and remount.
Controls must fail: a build without the flush correction, an acknowledgement before the sync, a damaged superblock pair, and for W8 the W8C window.

Limits of the model: the simulator has no timing, wear or mapping of its own; the replay covers the MMC stack, not an SD card; the writes come from this one workload per row.
**A model result is not evidence about a card, an eMMC device or a board.**

## Board evidence, not approved

One RT1060-EVKB and one microSD card of the product's part, with the rig `scripts/power_cut.py`. An eMMC product runs the same on its board and part.

| Step | Contents |
| --- | --- |
| Images | LittleFS variants of `tests/board_images/sd_card_power_cut_append` and `sd_card_power_cut_replace`, and a settings-save loop, each with the [mount rule](../file-contract.md#mounting-a-littlefs-volume) and no formatter. They do not exist yet |
| Provisioning | The card is formatted and given its directories by a separate, authorised step, whose tool and options the record names. No such route has been run |
| Cuts | At least 100 judged cuts for each of the three workloads, at random times during writes |
| Pass, every cut | The volume mounts without a format; the settings file holds the old or the new value; appended data is intact up to the last sync that returned success; a replaced file is the old or the new content, whole |
| Fail | Any cut that misses a criterion stops the campaign, and the card's image is kept |
| Also measured | Mount time and the first write after a mount, on the product's card size and fill level |
| Record | A new page under `docs/evidence/` with the revision, the configuration, the card identity, the rig, each cut's outcome and the limits. Model and board results stay apart |

A pass shows one board, one card and one revision. It qualifies no other card and gives no endurance result.
