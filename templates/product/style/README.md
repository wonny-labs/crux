# Style kit for a product repository

Format, patch-style and include checks that run from the root of a product repository. They add no Crux interface and no dependency, and they do not touch hardware. The rules they check, and what no check covers, are in [Zephyr and driver code in a product repository](https://github.com/wonny-labs/crux/blob/main/docs/coding-guidelines.md#zephyr-and-driver-code-in-a-product-repository) (`docs/coding-guidelines.md` in `crux`).

| File | Purpose |
| --- | --- |
| `.clang-format` | The format settings of this template's sources, equal to Crux's own: LLVM with Linux braces, 4 spaces, 100 columns |
| `.clang-tidy` | Crux's clang-tidy check list with a header filter anchored to the product root. Replace its `<PRODUCT_ROOT>` placeholder with the repository's absolute path, or pass `--header-filter` on the command line; unedited, it reports no header |
| `check-format.sh` | Runs `clang-format-18` in dry-run mode on every C and C++ file of the repository. Uses the product's `.clang-format`, or the copy in this directory when the product root has none |
| `check-patch.sh` | Runs Zephyr's `checkpatch.pl` from `ZEPHYR_BASE` on the C lines of a Git range, for the `BRACES` rule by default. It does not copy checkpatch, which is GPL-2.0 code |
| `check-includes.sh` | Runs `check_domain_includes.py --product` on the repository root, with the root resolved from Git |
| `target.clang-tidy` | An advisory clang-tidy profile for target code: Crux's selection without `-bugprone-easily-swappable-parameters`, and no `WarningsAsErrors`. It has no header filter to edit, and it is not named `.clang-tidy`, so clang-tidy does not pick it up by itself |
| `check_target_tidy.py` | Runs clang-tidy with that profile on the product's own sources in a Zephyr build's `compile_commands.json`. Findings never fail the run. See [Static analysis of target code](https://github.com/wonny-labs/crux/blob/main/docs/coding-guidelines.md#static-analysis-of-target-code) |

## Use them

Copy `style/` into the product repository and the two configuration files to its root, and set the product root in the copied `.clang-tidy`. Run the scripts from any directory inside the repository.

~~~sh
cp style/.clang-format style/.clang-tidy .
style/check-format.sh
ZEPHYR_BASE=<zephyr checkout> style/check-patch.sh origin/main HEAD
style/check-includes.sh --exclude app/src/legacy_threads.c
style/check_target_tidy.py build --exclude '^app/legacy/'
~~~

- `check-format.sh` needs `clang-format-18`, or the formatter that `CLANG_FORMAT` names. A nested `.clang-format`, such as Zephyr's file in the directory of an upstream-bound driver, applies only once the copy is at the product root. Without the root copy the script passes the kit's file with `--style=file:`, which clang-format applies to every file.
- `check-patch.sh` needs Perl, and a Zephyr checkout with `scripts/checkpatch.pl`. It runs from the product root. `CHECKPATCH_TYPES` widens the rule set, for example `BRACES,CODE_INDENT`. Zephyr's checkpatch expects tabs by default, so it reports every line of this template's 4-space code unless the types are limited.
- `check-includes.sh` runs the [include check](../README.md#check-the-whole-product-repository) that sits at the product root, or the one beside this directory. Every other argument goes to it.
- `check_target_tidy.py BUILD_DIR` needs Python 3 and clang-tidy 18, or the tool that `CLANG_TIDY` names, and the `compile_commands.json` of a Zephyr build (Zephyr v4.4.0 writes it by default). It analyses the sources of the Git top level that the database lists, outside the build directory. `--exclude REGEX` skips product paths, `--header-filter` changes the reported headers, and arguments after `--` go to clang-tidy. It exits 0 when it analysed every file, whatever it found, 1 when clang-tidy could not compile a file, and 2 on a usage error. It never passes `--fix`.
