# Style kit for a product repository

Format, patch-style and include checks that run from the root of a product repository. They add no Crux interface and no dependency, and they do not touch hardware. The rules they check, and what no check covers, are in [Zephyr and driver code in a product repository](https://github.com/wonny-labs/crux-pilot/blob/main/docs/coding-guidelines.md#zephyr-and-driver-code-in-a-product-repository) (`docs/coding-guidelines.md` in `crux-pilot`).

| File | Purpose |
| --- | --- |
| `.clang-format` | The format settings of this template's sources, equal to Crux's own: LLVM with Linux braces, 4 spaces, 100 columns |
| `.clang-tidy` | Crux's clang-tidy check list with a header filter anchored to the product root. Replace its `<PRODUCT_ROOT>` placeholder with the repository's absolute path, or pass `--header-filter` on the command line; unedited, it reports no header |
| `check-format.sh` | Runs `clang-format-18` in dry-run mode on every C and C++ file of the repository. Uses the product's `.clang-format`, or the copy in this directory when the product root has none |
| `check-patch.sh` | Runs Zephyr's `checkpatch.pl` from `ZEPHYR_BASE` on the C lines of a Git range, for the `BRACES` rule by default. It does not copy checkpatch, which is GPL-2.0 code |
| `check-includes.sh` | Runs `check_domain_includes.py --product` on the repository root, with the root resolved from Git |

## Use them

Copy `style/` into the product repository and the two configuration files to its root, and set the product root in the copied `.clang-tidy`. Run the scripts from any directory inside the repository.

~~~sh
cp style/.clang-format style/.clang-tidy .
style/check-format.sh
ZEPHYR_BASE=<zephyr checkout> style/check-patch.sh origin/main HEAD
style/check-includes.sh --exclude app/src/legacy_threads.c
~~~

- `check-format.sh` needs `clang-format-18`, or the formatter that `CLANG_FORMAT` names. A nested `.clang-format`, such as Zephyr's file in the directory of an upstream-bound driver, applies only once the copy is at the product root. Without the root copy the script passes the kit's file with `--style=file:`, which clang-format applies to every file.
- `check-patch.sh` needs Perl, and a Zephyr checkout with `scripts/checkpatch.pl`. It runs from the product root, and checkpatch uses the first `.checkpatch.conf` it finds there, then in `$HOME`, then in `.scripts`, so a user's `~/.checkpatch.conf` applies when the product has none. `CHECKPATCH_TYPES` widens the rule set, for example `BRACES,CODE_INDENT`. Zephyr's checkpatch expects tabs by default, so it reports every line of this template's 4-space code unless the types are limited.
- `check-includes.sh` runs the [include check](../README.md#check-the-whole-product-repository) that sits at the product root, or the one beside this directory. Every other argument goes to it.

## What was and was not run

Crux's tests run the three scripts on small throwaway repositories, with a stand-in for the tool where the real one is not installed, and the template's own sources through the real formatter. Nothing in Crux's CI runs them in a product workflow, and the `.clang-tidy` file has not been run on Zephyr driver sources. Its header filter is tested by applying the regex with Python to sample paths, not by running clang-tidy.
