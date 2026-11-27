# Flash safety check image

A compile-only image, not a sample, and never programmed. It places the FlexSPI NOR, MEMC and HAL routines that a
Flash write needs in ITCM for the RT1060-EVKB (`mimxrt1060_evk@B/mimxrt1062/qspi`), so that a script can inspect the
ELF. It makes no Flash write or erase call and activates no storage.

`scripts/test-flash-safety-check.sh` runs the fault tests of
`tests/native/flash_safety`, builds this image, and checks the ELF with `scripts/verify-flash-poc.py` and
`tests/native/flash_safety/test_elf.py`.

Background and recorded results: [Flash safety proof of concept](../../../docs/flash-safety-poc.md).
