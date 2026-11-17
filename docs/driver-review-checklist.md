# Driver review checklist

**Status: guidance, 2026-11-17. Not a Crux interface and not a check that any Crux CI job runs.** This page is for the author and the independent reviewer of a Zephyr device driver, and of the binding, Kconfig and tests that go with it, in a product repository that builds on Crux. It restates no rule: each section points to the rule in [Zephyr and driver code in a product repository](coding-guidelines.md#rules-for-driver-and-adapter-code), which holds the reasons and the Zephyr facts (read in Zephyr v4.4.0), and adds what a reviewer asks about the change around the rule. A product may adopt it as is or change it, as its [contribution guide](../templates/product/CONTRIBUTING.md) says.

## How to use it

The author copies the list into the pull request, and marks each item as done with the evidence (a file, a test name or a command and its result), or as `n/a` with the reason. The reviewer is someone who did not author the change. They read the driver, the binding, the Kconfig and the tests themselves, run or read the checks, and do not rely on the author's marks. They record `PASS`, `REVISE` or `ESCALATE` with the reasons, as [AGENTS.md](../AGENTS.md) defines the three for this repository:

- **Blocking finding:** an unmet acceptance criterion, a broken rule of the product's own standard, or a factual error. An item below that restates a rule is a criterion when it applies to the change. An item that begins "The reviewer asks" or "The reviewer reads" is a question. Its answer is a finding only if it shows an unmet criterion, a broken rule or a factual error.
- `PASS`: no blocking finding. `REVISE`: blocking findings that the author can fix inside the approved scope, followed by one independent re-check. `ESCALATE`: a finding needs a human decision, a material disagreement remains, or a blocking finding remains after the re-check.
- Other findings go to the issue, the pull request or a follow-up issue. They do not start another review round.

A passing check is evidence for the item it covers and nothing more. A `native_sim` pass is not hardware evidence, a host build is not a Zephyr build, and an advisory tool run is not a gate.

## Placement and the Crux boundary

Rule: the driver sits on the shell side, with the adapters ([choosing an API](choosing-an-api.md#the-rule-three-questions)).

- [ ] No upstream Zephyr driver already serves the part. If one does, the change is devicetree plus an emulator test, and the reviewer asks why a second driver is needed ([where a driver lives](shared-hardware-modules.md#where-does-this-board-or-driver-live)).
- [ ] The driver lives outside `domain/` and includes no `<crux/...>` header. `style/check-includes.sh` rejects the four frozen headers anywhere in a product. It does not reject other Crux headers outside `domain/`, so the reviewer reads the includes.
- [ ] A driver that includes a Crux header, or returns a Crux result type, is a finding: it has probably taken on product logic or a platform service.

## Binding

Rule: [Devicetree and Kconfig](coding-guidelines.md#rules-for-driver-and-adapter-code), and Zephyr's devicetree style page.

- [ ] The file is named after its compatible (`<compatible>.yaml`, or `<compatible>-<bus>.yaml` for a binding on a bus), and the `compatible` line matches the file name.
- [ ] Property names use dashes. No property says `required: false`, which is the default.
- [ ] The binding includes the bus binding that fits the part (`i2c-device.yaml` or `spi-device.yaml`) and the class binding where a class has one, as Zephyr's `fintek,f75303.yaml` does with `sensor-device.yaml` and `i2c-device.yaml`.
- [ ] The vendor prefix of the compatible is listed in `dts/bindings/vendor-prefixes.txt` under the module's `dts_root`. A public or example binding uses `vnd`.
- [ ] The reviewer asks whether every property that the driver reads is declared in the binding with a type and a description, and whether a default in the binding matches the default in the driver.
- [ ] The reviewer reads the board's devicetree node and the test overlay against the binding: the compatible, the bus address and the properties.

## Kconfig

Rule: [Devicetree and Kconfig](coding-guidelines.md#rules-for-driver-and-adapter-code) and [Prefixes](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] The driver symbol has `depends on DT_HAS_<COMPAT>_ENABLED`, with the compatible in upper case and underscores.
- [ ] Every new symbol is `CONFIG_<PRODUCT>_...`, never `CONFIG_CRUX_...`, and never in the `zephyr,` or `CRUX` namespaces.
- [ ] A symbol that defaults to `y` when its node exists is a deliberate choice. A reviewer asks which images contain that node, including a second image such as a bootloader, because Crux has not studied whether a module's devicetree-driven defaults reach a secondary image.
- [ ] The file follows Zephyr's Kconfig style (tabs, header comment). The product's `.clang-format` does not apply to it.

## Init level and priority

Rule: [Init level and priority](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] `POST_KERNEL` where the init function uses kernel services or another driver, such as the bus of an I2C or SPI part. `PRE_KERNEL_1` or `PRE_KERNEL_2` only for a reason written beside the macro.
- [ ] The priority comes from a Kconfig symbol, as a decimal literal or a symbolic name, never an expression. The device starts after the devices it uses.
- [ ] The author attached the order that `west build -t initlevels` printed, or `n/a` with the reason.
- [ ] A part that need not be ready at boot is a candidate for `zephyr,deferred-init`. The reviewer asks whether the code that uses it copes with a device that is not ready.
- [ ] The reviewer asks what the init function does when the bus is not ready or the part does not answer. By the return rule it returns an errno and does not carry on as if the part were there.

## Logging

Rule: [Logging](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] One `LOG_MODULE_REGISTER` per driver, in one source file. The others use `LOG_MODULE_DECLARE`.
- [ ] The log level comes from a Kconfig symbol, the class's or the driver's own.
- [ ] No `printk`, `printf` or Crux Logging call in the driver.
- [ ] The reviewer asks whether a path that is hit at every sample or every interrupt logs at `LOG_ERR` or `LOG_WRN`, which would flood the log, and whether an error is logged once.

## Return values and error paths

Rule: [Return values](coding-guidelines.md#rules-for-driver-and-adapter-code) and [Driver API](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] The API structure is defined with `DEVICE_API(class, name)`, `DT_DRV_COMPAT` is set, and the instances use `DEVICE_DT_INST_DEFINE` or the class macro. Zephyr's `DeviceAPI` compliance check flags a plain `struct x_driver_api` under `drivers/`.
- [ ] Every function returns 0 or a negative `errno`. `-ENOSYS` means supported but not implemented, `-ENOTSUP` means the hardware cannot do it. A bus error goes up unchanged.
- [ ] `__ASSERT` is for programming errors. A condition that can happen in normal operation, such as a part that does not answer, returns an error.
- [ ] The reviewer lists the error paths from the code: each early return, each bus call whose result is checked, each argument check, and each state check such as "not ready" or "busy". The list goes into the table of the emulator section, with the test that covers each path.
- [ ] The reviewer asks whether any error path leaves the device half configured, a lock held, a work item pending or a buffer in use.
- [ ] No `crux_status_t` or other Crux result type appears in the driver. The adapter translates the errno at its boundary.

## ISR and blocking rules

Rule: [ISR and blocking rules](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] The header comment of the driver says which API functions may be called from an ISR.
- [ ] An interrupt handler does bounded work and hands the rest to a thread (`k_sem_give`, `k_work_submit`, or `k_msgq_put` with `K_NO_WAIT`). It has no `K_FOREVER`, no mutex and no bus transfer that can sleep.
- [ ] A function reachable from both thread and ISR context tests `k_is_in_isr()`.
- [ ] Locks are `k_mutex` or `k_spinlock`, one kind per piece of state, never a Crux lock.
- [ ] The reviewer reads each shared variable once: who writes it, who reads it, and under which lock or in which context.

## DMA and cache

Rule: [DMA and cache](coding-guidelines.md#rules-for-driver-and-adapter-code). Mark the whole section `n/a` when the driver uses neither DMA nor a buffer that a device reads or writes.

- [ ] The buffer is flushed with `sys_cache_data_flush_range()` before the device reads it, and invalidated with `sys_cache_data_invd_range()` after the device wrote it and before the CPU reads it.
- [ ] The buffer is aligned and sized to the cache line, or placed in non-cached memory with `__nocache`.
- [ ] The buffer is static, not on a thread stack.
- [ ] The author states whether the cache is enabled and which memory is cacheable on the target. That is a fact to verify on the target, so the item stays open until a board run or an authoritative document settles it, and a `native_sim` test cannot close it.

## Power management

Rule: [Power management](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] If the part supports it, the driver follows the `PM_DEVICE_DT_INST_DEFINE` pattern of an upstream sensor driver such as `drivers/sensor/f75303`. If it does not, the item is `n/a`.
- [ ] The driver invents no power interface of its own.
- [ ] A suspend or resume path has an error path test, like any other path.

## Prefixes

Rule: [Prefixes](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] No `crux_`, `CRUX_` or `CONFIG_CRUX_` identifier, and no `zephyr,` binding prefix.
- [ ] Functions and types have the product's prefix, macros and enum constants its upper-case form.

## Emulator and `native_sim` tests

Rule: [Tests](coding-guidelines.md#rules-for-driver-and-adapter-code).

- [ ] The test runs on `native_sim` against an emulator or a fake, and a wired-part scenario is separate.
- [ ] A table lists every error path found in the error-path section against the test that triggers it and the assertion that proves the result. A path with no test is a finding, or a stated gap with the reason.
- [ ] The emulator can inject the failures that the paths need (a bus error, a part that does not answer, a wrong identity, an out-of-range value). A test that cannot reach a path is a missing emulator feature, not a missing test.
- [ ] The tests assert values and state, not only return codes: the data read, the register written, and that nothing was written on a refused call.
- [ ] The reviewer asks where the emulator's behaviour comes from. It should come from the part's data sheet, with an assumption that the data sheet does not settle written next to it.
- [ ] No assertion was weakened or removed to make a check pass.
- [ ] The report says what a `native_sim` run cannot show: cache coherency, DMA, interrupt timing, bus electricals and the real part's behaviour.

## Hardware scenario

Rule: [hardware integration tests](build.md#hardware-integration-tests).

- [ ] A part wired to a board has a scenario that is gated on a Twister fixture, so that CI builds it and does not run it.
- [ ] The pass or fail oracle is in the application's console output, so it does not depend on the route that runs it.
- [ ] CI is given no fixture name and no hardware map.
- [ ] The description says that a run is a hardware operation. It needs authorisation for the current task, a verified target, probe and flash configuration, and a safe setup, and it goes through the device-control route, not a Twister `--device-testing` or `--device-type=hardware` launch. The pull request records that no run happened, or the approval and the evidence of the run.
- [ ] A driver for a fictional or unwired part says that no hardware scenario exists, and why.

## Licence and SPDX

Rule: [CONTRIBUTING.md](../CONTRIBUTING.md) on third-party code, and the product's own contribution guide.

- [ ] Every new file has an `SPDX-License-Identifier` line (and a copyright line where the product requires one).
- [ ] Code modelled on a Zephyr source or on another upstream file names its source and keeps the licence terms (Apache-2.0 for Zephyr). A copy carries the upstream notice.
- [ ] No vendor SDK code, data sheet text or confidential material is in a public repository. A part under a confidential licence has its driver on a private remote ([licences and private remotes](shared-hardware-modules.md#licences-and-private-remotes)).
- [ ] No product, customer or person name is in an example, a comment or a test of a public repository.

## Checks to run before the review

The author runs them and records the revision, the command and the result. A check that was not run is listed as not run.

| Check | What it covers | Kind |
| --- | --- | --- |
| `style/check-format.sh` | Formatting of C and C++ files | Gate in the product's CI, if the product adds it |
| `style/check-patch.sh BASE HEAD` | `BRACES` rule of Zephyr's checkpatch on changed lines | As above |
| `style/check-includes.sh` | The four frozen headers anywhere, and the domain rules in `domain/` | As above |
| `style/check_target_tidy.py build` | clang-tidy on the product's own sources of a Zephyr build | Advisory ([how](coding-guidelines.md#static-analysis-of-target-code)) |
| Zephyr's `DeviceAPI`, `DevicetreeBindings`, `BoardYml`, `Nits` and `LicenseAndCopyrightCheck` compliance checks | `DEVICE_API`, binding names and properties, the board vendor, file hygiene, SPDX lines | As the [product runs them](coding-guidelines.md#zephyr-compliance-checks-out-of-tree); read from source, not run |
| The product's `native_sim` Twister run | Driver, emulator and tests | Evidence for the emulator section only |
| A cross-build for each board | The driver compiles and links for the target | Evidence that it builds, not that it works |

MISRA stays advisory ([position](coding-guidelines.md#misra-c-position)). A MISRA finding is a pointer for the reviewer, never a blocking finding by itself.

## Recording the review

Put this in the pull request, below the author's marked list:

~~~text
Reviewer: <name or agent>, not the author
Revision reviewed: <full SHA>
Sections read: <list, with n/a ones and why>
Checks seen: <command, revision, result; or "not run">
Verdict: PASS | REVISE | ESCALATE
Blocking findings: <item, evidence, what would close it>
Other findings: <issue or follow-up links>
Limits: <what this review did not check, for example hardware, cache behaviour, sysbuild images>
~~~
