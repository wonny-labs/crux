# Boot fixture

`zephyr/` is the application that the boot-composition checks build with sysbuild: `scripts/test-boot-composition.sh`,
`scripts/check-boot-config.py`, `tests/target/check_boot_images.sh`, `tests/target/check_boot_reproducibility.sh` and
`tests/target/compare-mcuboot-crypto-backends.sh`. Its folder name is the sysbuild image name, so it stays
`zephyr`. It runs the scenario of [`tests/time_periodic`](../time_periodic/README.md) (the sources are compiled from
there, so the two do not drift); it is not a sample and shows nothing about boot for a reader. For a product's boot
setup read [boot composition](../../docs/boot-composition.md).
