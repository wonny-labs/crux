# Coding and Public API Documentation Guidelines

## Purpose and scope

These guidelines apply to new or materially changed Crux-owned C17 code and public API declarations. They help contributors and AI coding agents produce consistent, reviewable code without changing the existing architecture or supported contracts. [CONTRIBUTING.md](../CONTRIBUTING.md) remains the entry point for contribution and review rules. Adopted [capability contracts](architecture.md#current-capability-integration) define supported behaviour.

Apply these rules incrementally. Do not reformat unrelated code, rename existing interfaces or convert every public header solely for consistency. External Zephyr, vendor and third-party sources follow their own requirements. The Zephyr code, drivers and devicetree of a product repository that builds on Crux are not Crux-owned; [the section on them](#zephyr-and-driver-code-in-a-product-repository) is guidance, not a Crux rule.

## Coding conventions

- **Language and portability:** Shared components use ISO C17. Public C declarations remain usable by the documented C++17 consumers through `extern "C"` where applicable. Do not leak OS, SoC, board or provider-private types into portable public headers. Qualified standard APIs are deliberate exceptions to Crux-owned interfaces, not general native access.
- **Formatting:** [.clang-format](../.clang-format) defines the owned-source style: LLVM-based formatting with Linux brace placement, 4-space indentation and a 100-column limit. The adopted change is limited to brace placement; keep all other settings from the configuration. Check with [`scripts/check-format.sh`](../scripts/check-format.sh) and the pinned formatter. Follow nearby code where a choice is not specified.
- **Clarity:** Use descriptive names and explicit units. Include braces on new or modified control-flow bodies, even for a single statement. Check range conversions and arithmetic when overflow would matter. Do not reformat unrelated code.
- **Changed-code patch style gate:** With `ZEPHYR_BASE` pointing to the pinned Zephyr workspace, run `scripts/check-patch.sh BASE HEAD` for the selected Git diff. The Bash wrapper calls pinned Zephyr `checkpatch.pl` with approved diagnostic types, initially `BRACES`. Pull-request CI compares the temporary merge commit to its first parent. Main-branch push CI compares `github.event.before` with the new HEAD, fetching the previous commit when necessary to cover multi-commit pushes. Manual CI dispatch checks the latest commit. The checker primarily rejects newly added unbraced control statements. **Limitation:** modifying only the body of a pre-existing unbraced `if` without changing its condition can pass this diff-based gate; code review must still apply the Clarity rule to such edits. Existing untouched legacy code and C++-only changes are outside the initial gate. No source rewrite, new analyser, Python compliance framework or MISRA compliance claim is introduced.
- **Logical spacing:** Separate top-level function definitions with one blank line. Inside functions,
  use at most one blank line between distinct stages. Keep same-purpose checks together and avoid
  padding individual statements or control-flow blocks. Keep rationale comments adjacent to their
  code; do not put blank lines immediately inside braces.
- **Includes:** Use angle brackets for public Crux, standard C and external public headers; use
  quotes for component-private and local headers. Group includes by role with one blank line where
  it improves navigation. Keep headers self-contained and preserve conditional or order-sensitive
  includes.
- **Organisation:** Group helpers, functions and declarations by responsibility, dependency and
  typical use flow. Keep declarations in dependency order and comments adjacent to their
  declarations or code. Do not impose a universal public/private layout or reorder code unless
  navigation clearly improves without changing dependencies or behaviour.
- **Naming:** Use `crux_` for public C functions, types and exported variables, and `CRUX_` for macros, enum constants and header guards, as defined in [CONTRIBUTING.md](../CONTRIBUTING.md#making-changes). Keep component-owned `<crux/...>` headers. Do not rename public targets, native providers or Zephyr identifiers for style alone.
- **Resources and errors:** Handle allocation, lifetime, cleanup after partial failure and concurrent access explicitly. Preserve adopted component-specific result types and named errors rather than forcing all APIs into one error enum.
- **Platform boundaries:** Portable consumers depend on public Crux contracts or explicitly qualified standard APIs. OS-specific ports and platform composition own native requirements. Do not introduce a universal HAL/OSAL or service registry without real consumer evidence.
- **Execution and safety:** Specify supported thread or ISR context, blocking, timeout units and resource limits. Do not promise real-time bounds, ISR safety, persistence or cross-OS equivalence without contract and evidence.

The existing [.clang-tidy](../.clang-tidy) selection, compiler warnings and tests are the configured automated checks. They are not a claim of full MISRA C, CERT C, security or functional-safety compliance. New mandatory checks and toolchain changes require separate justification.

## Output and logging

Each kind of code writes output in one way.
The rules follow Zephyr's [logging guide](https://docs.zephyrproject.org/latest/services/logging/index.html) and the usual library practice: a library reports status, and the application chooses where output goes.

| Code | Output |
| --- | --- |
| Drivers | Zephyr `LOG_*`, one log module per driver ([driver rules](#rules-for-driver-and-adapter-code)). No `printk`, `printf` or Crux Logging |
| Zephyr ports of Crux components (`components/*/ports/zephyr`) | Return a status. Use Zephyr `LOG_*` for a diagnostic only when one is needed. Add a per-component log level Kconfig symbol (`Kconfig.template.log_config`) when a port first logs, not in advance |
| Portable Crux components (`components/*/src`) | Return a status. Use Crux Logging only when a log record is part of the component's contract, as for security events |
| Product application | Zephyr `LOG_*` for diagnostics; `printk` for console lines that a person or a test harness reads |
| Samples and tests | `printk` on Zephyr and `printf` on Linux, one call per checked line. A test-only line inside a port is compiled only in test builds |
| The last message before a reset | `log_panic()` first (when `CONFIG_LOG` is set and not minimal), then the message, then the reset |

Crux Logging (`<crux/logging.h>`) is for portable code whose log record is part of its contract or that must log on both Linux Host and Zephyr.
It has no console provider; console lines use `printk` or `printf`.

## Public API consistency

Apply shared rules where they help consumers, without flattening capability-specific
contracts or renaming established APIs for style alone.

- **Names:** Follow the owning component's existing verb/object ordering. Prefer
  `out` for one unambiguous typed output, descriptive names for multiple outputs,
  and unit suffixes on raw integer time values. Retain `transferred` for byte counts.
- **Results:** `crux_status_t` uses zero for success and negative values for errors.
  File and Configuration have separate domains with meaningful positive outcomes.
  Compare named results within their domain, never cast between enums or treat all
  nonzero values as errors. Use the returned transfer count according to each API's
  documented partial-I/O semantics.
- **Time:** Existing bounded waits use `timeout_ms` (zero polls, finite positive
  range, no implicit FOREVER). Typed Duration and Monotonic values serve time
  arithmetic and absolute deadlines. Do not convert all existing waits for uniformity.
- **Lifetime:** Choose handle representation for the capability, not a universal
  pattern. Document failed creation, failed/contended cleanup, ownership transfer,
  and stale-handle use where callers must respond differently.
- **Context:** Use **thread context** in portable public contracts rather than
  OS-specific task terminology. State special ISR, pre-kernel and startup limits.
  Each component, not the shared context detector, decides call eligibility.
- **Compatibility:** This Pilot supports documented C17/C++17 source consumers
  without a stable binary ABI. Review incompatible API or behavioural changes and
  the necessary consumer migration before adoption. Avoid compatibility wrappers
  without demonstrated need and do not equate API maturity with target qualification.

## Public API documentation

For new or materially changed public declarations, use Doxygen-compatible `/** ... */` comments in the owning header. Existing untouched headers can be documented incrementally when relevant. A generated API site, Doxygen groups and a full-header conversion are not required by the current Pilot.

For multi-line Doxygen blocks, put `/**` on its own line and start the first text or
command (`@file`, `@brief`, etc.) on a following ` * ` line. Retain concise
single-line `/** Description. */` and member `/**< Description. */` forms.

Document the following when relevant to a caller:

- **Purpose and values:** Behaviour, accepted inputs, ranges, units, clock or time base, special values and prerequisites.
- **Outputs and errors:** Success and failure results, unchanged outputs, partial success, failure effects and retry or recovery rules.
- **Ownership and lifetime:** Ownership and validity of handles, buffers, callback contexts and stored references, including failure or close.
- **Execution context:** Blocking, timeouts, concurrency, re-entrancy, caller-side synchronisation and ISR limits.
- **Platform support:** Restrictions that affect the public contract, with detailed configurations and test evidence linked from the component contract.

Use an imperative one-sentence `@brief` or a clear first sentence. Document parameters in declaration order with `@param`. Use `@param[out]` and `@param[in,out]` for writable parameters where appropriate. Use `@retval` for discrete, actually possible status values and `@return` for general or provider-dependent results. Do not list unrelated errors or invent guarantees. Reserve `@note` and `@warning` for information that changes correct use.

Explain non-obvious type, enum, member and macro semantics with brief `/** ... */` or `/**< ... */` comments. Prefer meaningful guarantees and pitfalls over boilerplate: do not narrate implementation steps, restate identifiers or types, or add repetitive `@param`/`@return` text. Put shared constraints once at header level and use function comments for caller-specific differences. Keep design rationale and detailed verification in the capability contract.

## Review and validation

Review new or changed API declarations, documentation, implementation and focused tests together. Compare advertised outputs, errors, ownership, context and supported environments with actual behaviour. Record incompatible changes explicitly instead of treating documentation edits as API approval.

Use existing format, dependency, build and test checks proportional to the change. `scripts/analyze-host.sh` needs its documented configured Host build and analyses the sources that the builds listed in `scripts/tidy-sources.conf` compile (see [static-analysis coverage](static-analysis-coverage.md)). Documentation-only changes need link and accuracy review, not unrelated hardware tests.

## Zephyr and driver code in a product repository

Everything above covers Crux-owned C17 code. A product repository that builds on Crux owns its own Zephyr code: adapters, devicetree, Kconfig and device drivers. Crux does not own that code, adds no driver model or device API for it ([ADR-0001](decisions/0001-application-boundary-and-api-stability.md), [choosing an API](choosing-an-api.md)), and no Crux check enforces this section in a product repository. The section is guidance for a product team and for agents that work in such a repository. It is not a Crux interface, and a product may decide otherwise for its own code. The facts below were read in the Zephyr v4.4.0 sources. The Zephyr revision a product pins can differ, so check the linked page for it.

**Defer to Zephyr first.** For C style, devicetree, Kconfig, Doxygen and API design, follow Zephyr's own guidelines, which the [upstream list](#upstream-guidance) links, and the style of the nearest existing code. Two choices stay with the product. Formatting: Zephyr formats with 8-column tabs, while this repository and the [product template](../templates/product/README.md) use 4 spaces and 100 columns. Choose one style for a repository and keep it. A driver that is meant for upstream Zephyr is formatted with Zephyr's `.clang-format`. Naming: see the prefix rule below.

### Rules for driver and adapter code

A driver is Zephyr code. It lives on the shell side of the product, with the adapters, never in the domain (question 1 of [choosing an API](choosing-an-api.md#the-rule-three-questions)). It reaches the domain through a port that the product owns, and it needs no `<crux/...>` header. A driver that includes one has probably taken on product logic or a platform service.

- **Driver API.** Define the API structure of an upstream driver class with `DEVICE_API(class, name)`, so that it is placed in an iterable section. Zephyr's [migration guide for 4.1](https://docs.zephyrproject.org/latest/releases/migration-guide-4.1.html) says out-of-tree drivers should do so, and Zephyr's compliance check `DeviceAPI` flags a plain `struct x_driver_api` variable under `drivers/`. Set `DT_DRV_COMPAT` to the compatible with underscores, define instances with `DEVICE_DT_INST_DEFINE` or the class macro (for example `SENSOR_DEVICE_DT_INST_DEFINE`), and gate the Kconfig symbol with `depends on DT_HAS_<COMPAT>_ENABLED`. Zephyr's [device driver model](https://docs.zephyrproject.org/latest/kernel/drivers/index.html) is the reference.
- **Init level and priority.** Use `POST_KERNEL` when the init function needs kernel services or another driver, such as the bus of an I2C or SPI part. `PRE_KERNEL_1` and `PRE_KERNEL_2` run on the interrupt stack and may not use kernel services. Take the priority from a Kconfig symbol: the class's `CONFIG_<CLASS>_INIT_PRIORITY` where one exists, else the product's own. It is an integer from 0 to 999 and lower values start first. It must be a decimal literal or a symbolic name, never an expression such as `CONFIG_KERNEL_INIT_PRIORITY_DEFAULT + 5`. A device initialises after the devices it uses. Check the order that the linker produced with `west build -t initlevels`. A part that need not be ready at boot can use `zephyr,deferred-init` and `device_init()`.
- **Logging.** Register one log module per driver with `LOG_MODULE_REGISTER(name, CONFIG_..._LOG_LEVEL)` in one of its source files; its other source files use `LOG_MODULE_DECLARE(name, CONFIG_..._LOG_LEVEL)`. Either reuse the class's level symbol, as sensor drivers do with `CONFIG_SENSOR_LOG_LEVEL`, or give the driver its own through `subsys/logging/Kconfig.template.log_config`, as `drivers/eeprom/Kconfig` does. The other output rules are in [Output and logging](#output-and-logging).
- **Return values.** Return 0 on success and a negative `errno` on failure, as Zephyr's [API design guidelines](https://docs.zephyrproject.org/latest/develop/api/design_guidelines.html) say: `-ENOSYS` for an API that is supported but not implemented, and `-ENOTSUP` for an optional API or a combination of options that the hardware cannot do. Pass a bus error up unchanged. Use `__ASSERT` for programming errors and keep error returns for conditions that can happen in normal operation. `crux_status_t` and the other Crux result types never appear in a driver. The adapter translates the errno at its boundary into whatever the product's port declares.
- **ISR and blocking rules.** An interrupt handler does bounded work and never blocks: no `K_FOREVER`, no mutex, no bus transfer that can sleep. It hands the work to a thread with `k_sem_give`, `k_work_submit` or `k_msgq_put` with `K_NO_WAIT`. A kernel call from an ISR never uses another timeout. State in the driver's header comment whether each API function may be called from an ISR. Assume thread context only for a function built on a synchronous bus transfer, and test `k_is_in_isr()` where a function can be reached from both. A driver that guards its own data uses Zephyr's `k_mutex` or `k_spinlock`, never a Crux lock, and keeps one lock kind per piece of state (rule 3 of [coexistence in one image](choosing-an-api.md#coexistence-in-one-image)).
- **DMA and cache.** On a core with a data cache, flush a buffer with `sys_cache_data_flush_range()` before the device reads it, and invalidate it with `sys_cache_data_invd_range()` after the device wrote it and before the CPU reads it (`<zephyr/cache.h>`). Align and size the buffer to the cache line (`sys_cache_data_line_size_get()`, `CONFIG_DCACHE_LINE_SIZE`), or place it in non-cached memory with `__nocache`. This guideline adds a rule of its own: allocate DMA buffers statically, not on a thread stack. Whether the cache is enabled and which memory is cacheable depend on the SoC and the board image, so verify them on the target. `native_sim` has no cache and no DMA, so a test there says nothing about cache coherency. Zephyr's [cache guide](https://docs.zephyrproject.org/latest/hardware/cache/guide.html) has the rest.
- **Devicetree and Kconfig.** Follow Zephyr's devicetree and Kconfig style pages. Name the binding file after its compatible (`<compatible>.yaml`, or `<compatible>-<bus>.yaml` for a binding on a bus, which Zephyr's compliance check also accepts), write property names with dashes, and list each vendor prefix the product's compatibles use in `dts/bindings/vendor-prefixes.txt` under the module's `dts_root`. A Kconfig file is not C: the format and tidy settings of this repository do not apply to it, and Zephyr's Kconfig style asks for tabs.
- **Prefixes.** A product never uses `crux_`, `CRUX_` or `CONFIG_CRUX_` for its own identifiers: those namespaces belong to Crux, as in [Naming](#coding-conventions) above. Do not use the `zephyr,` prefix of Zephyr's own bindings either. Give product functions and types the product's own prefix, product macros and enum constants its upper-case form, and product Kconfig symbols `CONFIG_<PRODUCT>_...`. A public or example binding uses the `vnd` vendor prefix.
- **Power management.** If the part supports it, follow the `PM_DEVICE_DT_INST_DEFINE` pattern of an upstream sensor driver such as `drivers/sensor/f75303`. Do not invent a power interface.
- **Tests.** Test a driver on `native_sim` against an emulator or a fake, and keep a wired-part scenario separate, as [hardware integration tests](build.md#hardware-integration-tests) describes. A `native_sim` pass is not hardware evidence.

A reviewer or an author can walk these rules, and the files around a driver, with the [driver review checklist](driver-review-checklist.md). Each of its items points back here.

### What the Crux boundary check covers

The product-side include check, `templates/product/check_domain_includes.py`, is lexical. In `domain/` it rejects every `<zephyr/...>` header, the Crux composition interfaces, and four Crux headers: the three frozen ones (`<crux/thread.h>`, `<crux/sync.h>`, `<crux/serial.h>`) and the removed `<crux/queue.h>`. With `--product ROOT` it also rejects those four headers in every C, C++ and assembly source of the repository, driver sources included. [The template README](../templates/product/README.md#check-the-whole-product-repository) lists its rules.

It does not police anything else in this section. In particular it does not check:

- the product prefix rule, naming, or the use of `DEVICE_API`;
- init levels and priorities, logging, errno conventions, ISR and blocking rules, DMA and cache handling;
- devicetree, bindings and Kconfig, or any file that is not a C, C++ or assembly source;
- an include that arrives through a macro or a CMake include path, or a vendor header outside its short list (the Host build of the domain catches those).

`.clang-tidy` selects `readability-identifier-naming` without options, so it enforces no naming rule. `crux_assert_portable_consumer()` and the consumer boundary checker validate the documented build graph of portable consumer targets, not Zephyr driver libraries ([build guide](build.md#external-linux-application-using-crux-source)). The scripts that Crux's CI runs check Crux's own tree. A product repository is checked by them only if the product runs them itself.

### Checks from a product root

[`templates/product/style/`](../templates/product/style/README.md) holds what a product can copy: `.clang-format` and `.clang-tidy` (the format settings equal Crux's, and the tidy selection differs only in its header filter, which is anchored to a `<PRODUCT_ROOT>` placeholder that the product replaces with its absolute path, so that headers of Zephyr, Crux, the SDK and the build directory are not reported) and three wrappers that run from any directory of the product repository.

| Wrapper | What it runs |
| --- | --- |
| `check-format.sh` | `clang-format-18` in dry-run mode on every C and C++ file, with the product's `.clang-format` or the copy beside it. The copy is passed with `--style=file:`, which overrides any nested `.clang-format`, so a driver's own file applies only once the product root has its copy |
| `check-patch.sh` | Zephyr's `checkpatch.pl` from `ZEPHYR_BASE` on the changed C lines of a Git range, for the `BRACES` rule by default. The tool is not copied, because it is GPL-2.0 code that stays in Zephyr |
| `check-includes.sh` | `check_domain_includes.py --product` on the repository root |

Crux's own `scripts/check-format.sh` and `scripts/check-patch.sh` already work in any Git repository, since they use the Git top level of the current directory. What is specific to Crux is the `.clang-format` they read and the `BRACES`-only rule set. Zephyr's checkpatch expects tab indentation, and without `--types` it reports every line of 4-space code. That is why Crux limits its gate to `BRACES`.

### Static analysis of target code

`.clang-tidy` and `analyze-host.sh` analyse the sources that Crux's Host builds compile ([static-analysis coverage](static-analysis-coverage.md)). A product's Zephyr adapters and drivers are compiled only by a Zephyr build, so nothing in Crux analyses them. [`templates/product/style/`](../templates/product/style/README.md) holds an advisory way to do it: `check_target_tidy.py` and the profile `target.clang-tidy`. They add no Crux interface, and no Crux CI job runs them.

~~~sh
west build -b <board> app
style/check_target_tidy.py build
style/check_target_tidy.py build --exclude '^app/legacy/' -- --extra-arg=-Wno-unknown-warning-option
~~~

- **What it analyses.** The sources in the build's `compile_commands.json` that lie inside the Git top level of the product and outside the build directory. Zephyr, Crux, the SDK and generated sources are skipped. Headers are reported only under `app`, `domain`, `drivers`, `include` and `tests` of the product, and `--header-filter` changes that. `--exclude REGEX` skips product paths, such as code the product has not yet cleaned up.
- **Advisory.** Findings are printed and counted and never fail the run: the profile sets no `WarningsAsErrors`. The script exits 1 only when clang-tidy could not compile a file, because that file's result is missing, and 2 for a usage error or a missing tool or database. A product that wants a gate decides so itself, after it has seen the findings of its own code. Crux's rule that a new mandatory check needs a separate justification stands.
- **The profile.** It equals Crux's selection, which a test compares, except `-bugprone-easily-swappable-parameters`: a Zephyr driver API fixes parameter lists such as `(dev, reg, value)`, so the check is expected to report code that the product cannot change. That expectation comes from reading the check, not from a run. `readability-identifier-naming` has no options, so it enforces no naming rule here either.
- **The compile database.** Zephyr v4.4.0 writes `compile_commands.json` by default (`cmake/modules/kernel.cmake` sets `CMAKE_EXPORT_COMPILE_COMMANDS`); pass `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` if the pinned Zephyr does not. The database holds the build's own compiler command lines, for example GCC options for an Arm target. clang may reject an option it does not know, or not find the toolchain's headers. The script then reports the file as one that did not compile. Add `--extra-arg` options after `--` until the files compile.
- **Not run.** `check_target_tidy.py` is tested against a stand-in for clang-tidy, and against the real tool only where `CLANG_TIDY` names one. Neither the script nor the profile has been run on a Zephyr database, a `native_sim` database or a driver source, so the findings, the noise and the exceptions in the profile are unmeasured. Treat the first real run as a measurement and record it.
- **Other routes.** Zephyr can run analysers inside its build with `-DZEPHYR_SCA_VARIANT=<name>`. Its tree has the variants `clang` (the Clang static analyzer), `codechecker` (which runs Clang-Tidy, the Clang static analyzer and Cppcheck), `gcc`, `sparse` and `dtdoctor`, and variants for commercial tools (`coverity`, `cpptest`, `eclair`, `iar_c_stat` and `polyspace`). See Zephyr's [static code analysis](https://docs.zephyrproject.org/latest/develop/sca/index.html) pages. They are alternatives, and Crux has run none of them on product code.

### MISRA C position

Crux does not adopt MISRA C for product or driver code. MISRA stays **advisory**: it is not a gate, no check here or in CI fails because of a MISRA finding, and Crux makes no compliance claim for itself or for any product. [Static-analysis coverage](static-analysis-coverage.md) says the same of Crux's own code. Zephyr's [coding guidelines](https://docs.zephyrproject.org/latest/contribute/coding_guidelines/index.html) are a subset of MISRA C:2012 that Zephyr requires of its own new code. A product that wants a reference for style and safety can read that subset. It is guidance for product and driver code, not a requirement. The position is revisited when a certification or a customer requirement asks for MISRA, and the product then chooses the rule set, the tool and the deviation process.

To get an advisory MISRA signal on product code, run a checker over the same compile database. These commands come from reading the tools' documentation. None was run here, and the tools were not installed:

~~~sh
# Cppcheck with its MISRA addon over a Zephyr build's database (the open-source addon covers part of the rules)
cppcheck --project=build/compile_commands.json --file-filter='<product root>/*' --addon=misra.json
~~~

`misra.json` is Cppcheck's addon file, for example `{"script": "misra.py", "args": ["--rule-texts=<path>"]}`. The rule texts file comes from a licensed copy of the MISRA documents, so the product keeps it outside the repository and Crux ships none. Without it, as the addon's documentation describes, the findings carry rule numbers but not the rule wording. Read a result as a pointer for a reviewer, not as a verdict, and never as evidence of compliance. Commercial analysers with MISRA checkers, some of which Zephyr integrates as SCA variants, are the route for a compliance claim. Crux has evaluated none of them.

### Zephyr compliance checks out of tree

Zephyr's `scripts/ci/check_compliance.py` runs many checks, and each one is a separate name that `-m` selects (case-insensitive). Run it from the product root with `ZEPHYR_BASE` set, a range given with `-c`, and the Python packages of `scripts/requirements-compliance.txt` installed. Pass `-o` with a path outside the repository and `-n`, because it otherwise writes `compliance.xml` into the current directory, and a `<check>.txt` file there only for a check that fails or warns. Neither option stops DevicetreeLinting, when it lints a file, from writing `dts_linter.patch` into the current directory. Name the checks that suit the product, because the default runs all of them. **Not verified:** this note comes from reading the script at Zephyr v4.4.0. It was not run on a product repository, so every verdict below is a reading of the source.

Checks that make sense out of tree:

| Check | What it does for a product |
| --- | --- |
| Checkpatch | Runs Zephyr's `checkpatch.pl --no-tree` on the diff of the range, with no `--types` limit, from the product root. It uses the first `.checkpatch.conf` it finds in the working directory, then `$HOME`, then `.scripts`, so the product's own file applies, else a user-level `~/.checkpatch.conf`, and Zephyr's does not. Without either the defaults expect tabs. `style/check-patch.sh` is the `BRACES`-only form |
| ClangFormat | Runs `clang-format-diff.py` on the changed `.c` and `.h` files with the product's `.clang-format`. The script must be on `PATH`. It reports at notice level, which does not fail the run |
| DevicetreeBindings | For changed files under `dts/bindings/`: property names use dashes, no redundant `required: false`, and the file name equals the compatible. Skipped when no binding changed |
| DevicetreeLinting | Lints changed `.dts`, `.dtsi` and `.overlay` files with `dts-linter` through `npx`. It needs Node and `npm --prefix scripts/ci ci` done in the Zephyr tree, and skips itself without them |
| BoardYml | Reads every `board.yml` under the root and checks its `vendor` against Zephyr's and the module's `dts/bindings/vendor-prefixes.txt`. The module's file is found through `dts_root` in `zephyr/module.yml`, relative to the working directory |
| YAMLLint | Lints changed YAML files with Zephyr's `.yamllint`, never the product's, and reports warnings only |
| Gitlint (`-m` is case-insensitive) | Runs `gitlint` on the commits of the range with the product's `.gitlint`, or gitlint's defaults without one. Zephyr's own rules come only from a copy of its `.gitlint` and `scripts/gitlint` |
| Nits | For changed files: a final newline, no blank line at the start or end, the Kconfig header comment, no redundant `source`, no `...` separator in a binding. The binding rule looks only at `dts/bindings/` at the repository root |
| KeepSorted | Checks blocks that the product marks with `zephyr-keep-sorted-start`. It does nothing without such markers |
| CMakeStyle | For changed `.cmake` and `CMakeLists.txt` files: no tabs and no space in `if (`. It opens files relative to the working directory |
| LicenseAndCopyrightCheck | Uses the `reuse` package to warn when a changed text file lacks an SPDX license or copyright line. It needs `reuse` and libmagic and gives warnings only |
| DeviceAPI | Flags a `struct *_driver_api name =` definition in a `.c` file whose path starts with `drivers/`, except types whose name contains `emul`. It sees only types named `*_driver_api`, and only a `drivers/` directory at the repository root |
| DeviceMmioCheck | Skips itself in v4.4.0 ("Check disabled pending documentation and community discussion"), so it checks nothing for any path |

`GitDiffCheck`, `BinaryFiles`, `TextEncoding` and `ImageSize` also read only the diff and the working tree. By their source they work in any repository, and were not run either.

Checks that do not make sense for a product:

| Check | Why not |
| --- | --- |
| Kconfig, KconfigBasic, KconfigBasicNoModules, KconfigHWMv2 and the Sysbuild variants | They check Zephyr's own Kconfig tree: the top-level `Kconfig` of `ZEPHYR_BASE`, and `git grep` for symbol use in Zephyr's `tests`, `samples` and `modules` and in the active west projects. **Not verified:** whether they follow a product's Kconfig, and whether their undefined-symbol results for product symbols mean anything. A Kconfig error in a product shows in its real build anyway |
| Identity | Requires a `Signed-off-by` line that matches the commit author, with a real e-mail address. It applies only to a product that adopts sign-off, and a product that does not would fail every commit |
| MaintainersFormat, ModulesMaintainers | They read Zephyr's `MAINTAINERS.yml` format. They do nothing in a repository without that file |
| ZephyrModuleFile | Checks that the Zephyr tree itself has no `zephyr/module.yml`. It looks at `ZEPHYR_BASE`, not at the product |
| SphinxLint | Lints reStructuredText files only |
| PyLint, Ruff, PythonCompat | Python checks with Zephyr's `pylintrc`, the repository's Ruff configuration, and a Python 3.12 version ceiling. A product's Python tooling follows its own rules |

## Upstream guidance

These references inform selected practices. They do not override Crux's established formatting, public contracts or review rules.

- [Zephyr C Code and General Style Guidelines](https://docs.zephyrproject.org/latest/contribute/style/code.html)
- [Zephyr Devicetree Style Guidelines](https://docs.zephyrproject.org/latest/contribute/style/devicetree.html)
- [Zephyr Kconfig Style Guidelines](https://docs.zephyrproject.org/latest/contribute/style/kconfig.html)
- [Zephyr Doxygen Style Guidelines](https://docs.zephyrproject.org/latest/contribute/style/doxygen.html)
- [Zephyr API Design Guidelines](https://docs.zephyrproject.org/latest/develop/api/design_guidelines.html)
- [Linux kernel coding style: Commenting](https://docs.kernel.org/process/coding-style.html)
- [Pigweed C++ style](https://pigweed.dev/style/cpp.html)
