# Vendor kits across repositories

**Status: Experimental, a recommended convention, 2026-11-17. Not adopted as a platform commitment.** This page adds to the [Product Composition Guide](product-composition.md) for an organisation that builds products from one or more vendor kits: source, libraries and identity files that a vendor delivers, in numbered deliveries, on more than one maintained line. It recommends how the kit, the module that compiles it and the products that use it fit together, how a build proves which delivery it compiled, and what a release records. Where the Product Composition Guide already says something, this page links to it and does not repeat it. What was run, and what was not, is in [Limits](#limits).

The names `acme`, `acmeco`, `kit-a`, `kit-a-module`, `product-x`, `git.example` and every delivery number on this page are invented.

## Terms

| Term | Meaning |
| --- | --- |
| Kit | What a vendor delivers for one product family: sources, prebuilt libraries, headers, and licence and identity files |
| Line | A maintained series of deliveries that stay compatible with each other, such as `1.x` and `2.x`. A new line is usually a vendor's major or service-pack release |
| Delivery | One numbered drop of a line, as received, such as `1.1.0` |
| Kit repository | The organisation's internal Git repository that holds the deliveries of one kit, on the [vendor branch](product-composition.md#vendor-branch) pattern |
| Kit module | A Zephyr module, owned by the organisation, that compiles the kit for Zephyr and Crux: CMake, Kconfig, glue code and the committed hash lists of the deliveries it accepts |
| Product | A product repository, as in the Product Composition Guide. It pins one line of each kit it uses |

## Who holds what

| Part | Lives in | Owner | Never in |
| --- | --- | --- | --- |
| Kit sources, as delivered | The kit repository, branch `vendor-<line>`, one commit per delivery | The organisation, with a named owner per kit, as for a fork | Any public repository, Crux included |
| Local changes to the kit | The kit repository, branch `work-<line>` | The same owner | Any public repository |
| Licence and identity files of the kit (licence keys, device identity masks, signed vendor certificates) | Outside every repository. The build reads them from a path, and the module holds only their expected SHA-256 | The product owner | Any repository, public or internal. See [Licence and identity inputs](#licence-and-identity-inputs) |
| Glue code, CMake, Kconfig, hash lists | The kit module | The organisation | A public repository, if the glue code itself reveals licensed material |
| The pin of a kit line | The product manifest, or the organisation manifest | The product owner | |

Code under a vendor licence may enter the kit repository only if that licence allows it to be held on the organisation's Git server. If it does not, or if that question is still open, keep the delivery outside Git, as [Deliveries held outside Git](#deliveries-held-outside-git) describes.

## Kit integrity

The build of a kit module checks that the kit tree it compiles is a delivery the module knows, and says which.

### The mechanism

1. **The list.** For every regular file of the kit tree, take the SHA-256 of its bytes. Write one line per file, `<hex digest>  ./<path>`, sorted by the bytes of the path. A `.git` entry at the top of the tree is left out, so a west project checkout and an unpacked archive give the same list. A symbolic link, or a file name with a newline, is refused, because the list cannot state it without ambiguity. This is the list that the Product Composition Guide's [vendor branch](product-composition.md#vendor-branch) section writes with `find . -type f -exec sha256sum {} + | LC_ALL=C sort -k 2`, in the same format.
2. **The digest.** The SHA-256 of the list's bytes identifies the tree. A changed byte, an added, removed or renamed file all change it.
3. **The committed lists.** The kit module holds one list per accepted tree, at `kit-hashes/<line>/<delivery>.sha256`. A delivery as received is named by its delivery, `kit-hashes/1.x/1.1.0.sha256`. A released state of a working branch, when the product compiles one, is named after its work tag without the `work/` prefix, `kit-hashes/1.x/1.1.0-acme1.sha256`.
4. **The check.** At configure time the module computes the list of the tree it is about to compile and compares it byte for byte with each committed list. Exactly one must match.

The build output then names what matched, for example:

```text
-- kit-a: line 1.x, delivery 1.1.0, hash list 3f1c...e9, from /work/modules/kits/kit-a (west project)
```

### Unknown delivery: warn in development, fail in a release

A tree that matches no committed list is an unknown delivery.

| Build | Result | Why |
| --- | --- | --- |
| Development | CMake warning, the build continues, and the output marks the build as not a release candidate | A developer must be able to try a new delivery, or a local change, before its list is committed |
| Release (`-DPRODUCT_RELEASE_BUILD=ON`, see [Marking a release build](#marking-a-release-build)) | Configure error | A release must compile a tree that the module was built and tested against |
| Any build with `-DKIT_REQUIRE_KNOWN_DELIVERY=ON` | Configure error | For a CI job that must not pass on an unknown tree |

Two committed lists with the same content are an error, because the match would not name one delivery. A product that pins a kit revision and a module revision that do not belong together gets an unknown delivery, so the check also catches that.

### Reference template

[`templates/kit-module/`](../templates/kit-module/README.md) holds a reference of the check, tested by `tests/build/test_vendor_kit_template.py`:

- `kit_hashes.py generate <kit-dir>` prints the list of a tree. `kit_hashes.py check <kit-dir> --lists kit-hashes [--expect-line 1.x]` prints `MATCH line=... delivery=... digest=...` and exits 0, or `UNKNOWN digest=...` and exits 1. It needs Python 3.9 or later and nothing else.
- `kit_integrity.cmake` defines `kit_integrity_check(NAME ... ENV_VAR ... DEFAULT_PATH ... HASH_DIR ... [EXPECT_LINE ...])`, which runs the check, applies the [path rule](#the-kit-path-rule) and the release rule, and sets `KIT_INTEGRITY_LINE`, `KIT_INTEGRITY_DELIVERY`, `KIT_INTEGRITY_DIGEST`, `KIT_INTEGRITY_PATH` and `KIT_INTEGRITY_SOURCE` for the caller, for example to write them into a generated header or the build directory.

The check runs at configure time. A kit file changed after configuring is not seen until CMake runs again, which a release from a fresh workspace always does. Both files are a template, not a Crux interface, and neither has been run inside a Zephyr build.

### Whole tree or the files compiled

The template lists the whole tree. A second shape lists only the files the module compiles: the kit repository keeps the full list of each delivery, and the module keeps, per delivery, the subset it uses, with a module CI step that checks the subset against the full list.

| Choose | When |
| --- | --- |
| Whole tree (the template) | The default. It also catches a stray file that a source glob or an include path could pick up, and a dirty tree |
| Files compiled | The delivery holds large parts the module never reads, such as IDE projects or tools for another host, and their churn would make every list differ. The module must then list its sources explicitly, never by glob |

### Receipt of a delivery

A hash list taken after unpacking proves that the vendor branch equals what was unpacked, not what the vendor sent. Recommended, for each delivery, a receipt kept beside the hash list in the kit repository's working branch or in the module:

- the SHA-256 of each archive as received, and the vendor's own checksum or signature if the vendor gives one, with the result of checking it;
- the channel, the date and the role that received it;
- where the archive is kept: internal storage that does not allow a stored object to be replaced, readable by the roles that may rebuild a release.

Import each delivery into a clean working tree (`git clean -fdx` first), with `core.autocrlf=false`, and refuse symbolic links, so that what git stores is what was received. Then check the delivery tag against its list, as the [vendor branch](product-composition.md#vendor-branch) section shows. Sign the `vendor/*` and `work/*` tags if the organisation's Git server can verify tag signatures.

## A worked example: one kit, two lines

`kit-a` is delivered on two maintained lines. Line `1.x` is in the field; line `2.x` is the vendor's newer service-pack line.

### The kit repository

The repository follows the [vendor branch](product-composition.md#vendor-branch) commands of the Product Composition Guide, which already show deliveries `1.0.0`, `1.1.0` and `2.0.0` and a fix delivery on the older line. After those steps it holds:

| Ref | Kind | Points to |
| --- | --- | --- |
| `vendor-1.x` | Branch | The latest delivery of line `1.x`, as received |
| `work-1.x` | Branch | Line `1.x` with the organisation's local changes, each delivery merged |
| `vendor-2.x`, `work-2.x` | Branches | The same for line `2.x`. `work-2.x` started from `work-1.x`, so local changes carry over and each is reviewed at the merge |
| `vendor/<delivery>` | Annotated tag | Each delivery as received, such as `vendor/1.1.0`, `vendor/1.1.1`, `vendor/2.0.0` |
| `work/<delivery>-<org><n>` | Annotated tag | Each released commit of a working branch, such as `work/1.1.1-acme1`, `work/2.0.0-acme1`. The delivery in the name is the last one merged |

Local commits on a working branch use the subject tags and `Upstream-Status` trailers of [soft forks](product-composition.md#soft-forks). A change that must never reach the vendor or any public repository is tagged `[acme noup]` and its trailer says why.

### Two shapes for the kit module

A product builds against exactly one kit line. The module can serve two lines in one of two shapes.

| | Shape A: one module line per kit line | Shape B: one module line for two kit lines, for a bounded transition |
| --- | --- | --- |
| Branches | `release-kit-1.x` for kit line `1.x`, `main` for kit line `2.x` | `main` only |
| Tags | `v1.y.z` build kit line `1.x`, `v2.y.z` build kit line `2.x`. The module's major version follows the kit line, which fits the [shared module rule](shared-hardware-modules.md#versions-and-pins) that a change a product must act on is a major change | One series, `vX.Y.Z`. Each tag's release notes state which kit lines and deliveries were built and which were tested on a board |
| Code differences | Each branch holds only its line's code | Small version guards, collected in one table or header, selected by the line that the product configures |
| Hash lists | Each branch holds `kit-hashes/<its line>/` only | `kit-hashes/1.x/` and `kit-hashes/2.x/` |
| A module fix for both lines | Made on `main`, then `git cherry-pick -x` onto `release-kit-1.x`, with a `[acme fromtree]` subject | One commit |
| Ends when | The last product on kit line `1.x` reaches the end of its support period | The older line is dropped once the newer line has run on a board for every product that moves; the transition has an end date |

**Criterion.** Choose B while the differences between the lines fit in one table of version guards and the older line is being retired. Choose A as soon as the guards stop being small (whole files differ, or the guards spread through the glue code) or the older line must be maintained for a product's full support period. Moving from B to A is cheap: branch `release-kit-1.x` from the last tag that built `1.x` and remove the `1.x` guards from `main`.

In both shapes the product selects its line in Kconfig, for example a string symbol `CONFIG_ACMECO_KIT_A_LINE="1.x"`, and the module passes it as `EXPECT_LINE`, so a product configured for one line that points at a tree of the other fails at configure time. A module may also compare the kit's own version header with that line. The template tests only the hash-list line.

### What the product's manifest shows

The product pins the kit and the module by full SHA, with the tag in a comment, like every other project ([Soft forks](product-composition.md#soft-forks)). The tag names are recorded in the release record; west resolves the SHA.

```yaml
manifest:
  version: "1.2"
  # Restricted kits are off by default, so that a reader without access can
  # fetch and build the rest. CI that holds the token enables the group.
  # group-filter: [+acme-kit-a]
  remotes:
    - name: crux
      url-base: https://github.com/wonny-labs
    - name: acme
      url-base: https://git.example/scm/acme
  projects:
    - name: crux-pilot
      remote: crux
      revision: <Crux SHA>
      import: true
    - name: kit-a
      remote: acme
      revision: 0123456789abcdef0123456789abcdef01234567 # work/1.1.1-acme1
      path: modules/kits/kit-a
      groups: [acme-kit-a]
    - name: kit-a-module
      remote: acme
      revision: 89abcdef0123456789abcdef0123456789abcdef # v1.3.0
      path: modules/kit-a-module
      groups: [acme-kit-a]
  self:
    path: product-x
```

`west crux-pins` reports both as `PRODUCT`. A product that uses the organisation manifest gets the same entries from there, as for a [shared hardware module](shared-hardware-modules.md#what-a-module-changes-in-the-checks).

The path, `modules/kits/kit-a`, does not change with the line. The revision carries the line, so a move to line `2.x` changes revisions only.

### Applying a fix delivery to line 1.x

1. The kit owner imports delivery `1.1.1` on `vendor-1.x`, checks it against its list and receipt, tags `vendor/1.1.1`, merges it into `work-1.x`, resolves and reviews any conflict, and tags the released commit `work/1.1.1-acme1`. Line `2.x` is not touched.
2. The module owner adds `kit-hashes/1.x/1.1.1.sha256` and, if products compile the working branch, `kit-hashes/1.x/1.1.1-acme1.sha256`, builds and tests, and tags the module (`v1.3.0` in shape A, or the next tag of `main` in shape B, with "built: 1.x at 1.1.1" in its notes).
3. Each product on line `1.x` moves both pins in one change, runs its checks and makes a new product version, as in [Upgrades and security fixes](product-composition.md#upgrades-and-security-fixes).

### Moving a product from line 1.x to line 2.x

1. Check that the module has a tag that builds and tests line `2.x` at the wanted delivery: a `v2.y.z` tag in shape A, or a tag whose notes list `2.x` as built and tested in shape B.
2. In the product, in one change: move the `kit-a` pin to the `work/2.0.0-acme1` SHA, move the `kit-a-module` pin to that module tag, and change `CONFIG_ACMECO_KIT_A_LINE` to `"2.x"`.
3. Build. The configure output must now name `line 2.x, delivery 2.0.0`. Run the product's tests and the release checks.
4. Record in the release notes that the kit line changed. Decide on the security counter as for any other upgrade.

## The kit path rule

- **Default.** The module reads the kit from its west project path, through the variable `ZEPHYR_<NAME>_MODULE_DIR` if the kit's working branch carries a `zephyr/module.yml` (added as a `[acme noup]` commit), or otherwise from a path that the kit module derives from the west workspace. In Zephyr v4.4.2, `scripts/zephyr_module.py` emits a module that has a `zephyr/module.yml` without a `build:` section with an empty CMake directory, and `cmake/modules/zephyr_module.cmake` still sets `ZEPHYR_<NAME>_MODULE_DIR` for it. That was read in source, not built.
- **Override for local development only.** An environment variable, one per kit (`KIT_A_PATH` in the template), may point the build at another tree. The build prints it as a CMake warning with the path, and the integrity check still runs on that tree.
- **Refused in a release build.** A release build stops if the variable is set. It also stops if `EXTRA_ZEPHYR_MODULES` or `ZEPHYR_EXTRA_MODULES` is set, in CMake or in the environment, because a module added that way replaces or adds a tree that the build record and `west crux-pins` do not see. Zephyr v4.4.2 reads both names, from either place, in `cmake/modules/zephyr_module.cmake` (read in source). The Product Composition Guide's [shared hardware module page](shared-hardware-modules.md#local-development) already says never to release such a build; the check makes that a configure error.
- **A checkout that left its pin.** `west crux-pins` reports `MISMATCH` for a project whose `HEAD` is not what `west update` fetched, for any active project, not only those Crux pins ([`west crux-pins`](product-composition.md#west-crux-pins); read in `scripts/west_commands/crux_pins.py`), so the release flow catches a kit checkout moved by hand.

An override through a CMake cache variable was considered and is not recommended: a cache variable persists silently in a build directory, while an environment variable has to be present in each shell that builds.

### Marking a release build

Recommended: the CMake cache variable `PRODUCT_RELEASE_BUILD`, set with `-DPRODUCT_RELEASE_BUILD=ON` on the release build command, beside `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON` ([Release](product-composition.md#release)). Every kit module of the product reads the same variable. A CMake variable, rather than a Kconfig symbol, keeps `.config`, and so `firmware_identity`, the same for a development and a release build of the same tree, and is visible to module CMake before any kit source is added. The release record states that the flag was set. An organisation may give the variable its own prefix, as long as all its modules agree.

## Licence and identity inputs

Licence keys, device identity masks and similar inputs that come with a delivery are never committed, to any repository. The module holds their expected SHA-256, and the build reports the hash it found, never the file.

How a release build receives their path is open:

| Option | How | For | Against |
| --- | --- | --- | --- |
| A, recommended | A CMake cache variable on the release command, such as `-DKIT_A_LICENCE_FILE=<path>`, checked against the expected hash | The input appears in the build command, which the release record keeps | A path outside the workspace |
| B | An environment variable, as for development, allowed in release builds for these inputs only, still checked against the expected hash | One mechanism for all builds; fits a CI secret store | The build command does not show it, and it differs from the kit path rule above |

In either option a missing or mismatching file stops a release build. The template does not implement this part.

## Deliveries held outside Git

When the licence does not allow a delivery on the organisation's Git server, or that is still undecided, or the delivery is large and partly binary or generated:

- Keep each archive as received in internal storage that keeps every version, fetched by its hash, as Zephyr's `west blobs` does for binary blobs ([Zephyr binary blobs](https://docs.zephyrproject.org/latest/contribute/bin_blobs.html)).
- The module reads the unpacked tree from a fixed path in the workspace, or, during development, from the override variable, and runs the same integrity check. The vendor branch pattern is not used, and there is no work tag.
- A local change is held as a patch in the module, applied to a copy at configure time, and listed in the release record. Prefer this only until the licence question is answered.
- The release record says "sources held outside Git" for that kit, with the archive hash, the hash-list digest and where the archive is kept. A tree identified only by a hash-list digest is weaker than a tag in Git, because nothing records how it came to be, but it is exact about what was compiled.

This is the [route "Delivery that may not enter the repository"](product-composition.md#modifying-third-party-code) of the Product Composition Guide, made concrete.

## Other content of a kit

- **Prebuilt libraries.** Record each library's hash in the hash list, as for a source file. A library the delivery lacks, such as a cryptographic library that the vendor expects the integrator to supply, comes from its own project or delivery with its own record. A stub that only satisfies the linker proves nothing about the real library.
- **Third-party stacks inside a kit.** Where a kit bundles a public stack, prefer to take that stack as a separate west project pinned in the product, so that its licence and version appear per product, and to use the kit's copy only if the vendor requires it.
- **Per-product component lists.** When products enable different parts of a kit, generate the list of compiled sources from a base list, the product's options and the product's additions, and check at configure time that the sources added to the build equal that list. A product's list is then a reviewable file.
- **Per-product device identity.** An identity value that the vendor delivers as a mask or a header stays outside the repositories, like a licence input. A product override within that mask is a product file, reviewed and recorded.
- **Changing kit code.** The working branch, with a subject tag and an `Upstream-Status` trailer on each commit; never licensed bytes in a public repository; each change listed in the release record's carried-changes list.

## Restricted kits, public repositories and CI

These points come from a public reference product that pins Crux by full SHA. They were inferred in that work, not tested.

- **Groups off by default.** Put each restricted kit and its module in a group that the product manifest does not enable, so that a reader without access can fetch and build everything else, and the default CI jobs pass without any secret.
- **One job per restricted group.** A job that enables only that group holds a read-only token. Pull requests from forks never receive repository secrets, so such a job runs only on branches of the repository itself.
- **Guard the group list.** A product that wants to stop an accidental `+group` can keep a list of known optional groups and refuse any other in CI, in the default and in each group-on mode, before fetching. Each new restricted kit then needs a guard entry, a choice between a `name-blocklist` now and a dedicated group, and its job. A guard that matches projects by name should also check the URL, because a soft fork keeps the upstream name.
- **Release group setting.** Set the groups that a release needs in the product manifest, not only in local `manifest.group-filter` configuration. `west manifest --freeze --active-only` leaves inactive projects out (west 1.4.0 `manifest.py`, read in source, not run), so a freeze made where the kit group is off, or made without access to the kit, silently omits the kit. After `west init --mf` from the lock, check that every kit the product needs is present and active.
- **The lock of a public product.** The frozen manifest of a build with restricted kits names internal URLs and SHAs. A public product repository then keeps that lock in the internal release record, not in the public tree, and its public bundle holds hashes only. The [release bundle checker](release-bundle-checker.md) has no rule for internal URLs today. How the public lock and the internal lock relate is an [open question](#open-questions).
- **Reachability.** A release can be rebuilt years later only if every pinned commit stays reachable and every archive stays readable. Keep a durable tag on each released SHA, mirror the public upstreams internally, and record, per restricted input, where it is archived and which role may retrieve it.

## Manifest layering

Exactly one manifest should pin Crux. If two layers pin it, west's first-definition rule ([Composition](product-composition.md#composition)) picks one without a warning. `west crux-pins` reads the contract from the Crux revision that the resolved manifest holds, so it checks the result, not the intent.

The existing templates use option A. Option B came from the reference product work.

| | A: the organisation manifest pins Crux (current [shared hardware module](shared-hardware-modules.md#versions-and-pins) guidance) | B: only the product manifest pins Crux |
| --- | --- | --- |
| Layering | Product imports the organisation manifest, which imports Crux | Product imports Crux and the organisation layer; the organisation layer holds modules and kits and does not import Crux, or imports it filtered out with a `name-allowlist` |
| Baseline | One Zephyr baseline per organisation, and the shared module's CI tests exactly that | Each product moves its baseline on its own; a shared module's CI covers only the baseline it was run on |
| Risk | A product that also names `crux-pilot` overrides the organisation's pin; visible in the product manifest | Products drift apart, and a module tag may not have been built against a product's baseline |

This page does not change the accepted guidance. B is listed for the owner's decision. In both, give the organisation's projects a name prefix, because west project names are global; put a product entry before the import when an override is intended; and consume driver and kit modules as Zephyr modules (`board_root`, `dts_root`, module CMake), never by including their files from product sources. Adding or changing a module that takes part in an image build changes `firmware_identity` ([Identity](product-composition.md#identity)), so treat it as a pin move with identity evidence.

## What a release records

The [release record template](../templates/product/RELEASE.md) gains a section for vendor kits and a section for the build environment. For each kit: the line, the delivery tag, the work tag, the commit SHA, the hash-list digest that the module printed, the receipt hash, the location (west project, or sources held outside Git), the licence record, and the module tag that compiled it.

The provisional [release manifest schema](release-bundle-checker.md) has `vendor_deliveries` with a project, a delivery tag and the hash of its hash list. Its delivery tag pattern now accepts the `vendor/<delivery>` and `work/<delivery>-<org><n>` forms of the vendor branch section; it refused the slash before. Everything else on this page goes into the manifest's `extensions` object until the schema is extended. A proposed shape for that extension, a `kits` list (name, line, delivery, delivery tag, location, commit, hash-list hash, receipt hash, licence reference) and a `modules` list (name, tag, commit, kit lines built and tested), is an [open question](#open-questions) and is not in the schema.

The best evidence that a record is complete is a rebuild: two builds from the frozen manifest in fresh workspaces at different paths give the same image hash and `firmware_identity` ([Identity](product-composition.md#identity)). Record that result.

## Where this follows or differs from common practice

Sources opened on 2026-11-17. "Verified" means the statement was read on that page; nothing here was run against those tools except where a row says so.

| Practice in this guide | Common practice | Source and what was verified | Follows or differs |
| --- | --- | --- | --- |
| Product repository as the west manifest repository, Crux and Zephyr imported, entries in the product win | West: the first definition of a project name wins; imports in `self` come first, then the manifest's own projects, then project imports | [west manifests](https://docs.zephyrproject.org/latest/develop/west/manifest.html): verified the first-definition rule and import order | Follows |
| Optional groups off by default, enabled with `group-filter: [+group]` | West: all groups are enabled unless the manifest or configuration disables them with `-`. Android repo: a project in the `notdefault` group is not synced unless asked | [west manifests](https://docs.zephyrproject.org/latest/develop/west/manifest.html) and the [repo manifest format](https://gerrit.googlesource.com/git-repo/+/HEAD/docs/manifest-format.md): verified both | Follows; the off-by-default state comes from Crux's manifest disabling the group, not from west |
| Pin by full SHA, tag in a comment, frozen lock for a release | West: `west manifest --freeze` rewrites each revision to a SHA, and the page warns that following a branch gives no reproducible `west update`. Repo: a revision may be a SHA, though its page says SHAs "have not been extensively tested" | Both pages above: verified | Follows |
| Vendor branch: each delivery imported unmodified, tagged, merged into a working line; files the vendor dropped are removed | The classic vendor branch: import each drop on a vendor line, tag it, merge the difference into the local line; removed files must be deleted by hand or by a helper script | [Version Control with Subversion, "Vendor Branches"](https://svnbook.red-bean.com/en/1.7/svn.advanced.vendorbr.html): verified | Follows. One vendor branch per line is this guide's addition, for fix deliveries on an older line |
| Hash list in `sha256sum` format, sorted, digest of the list | Go's module directory hash `h1:` is the SHA-256 of sorted `sha256sum`-style lines, base64-encoded. SPDX 2.3's package verification code is the SHA-1 of the sorted per-file SHA-1 values, without file names | [Go dirhash](https://pkg.go.dev/golang.org/x/mod/sumdb/dirhash) and [SPDX 2.3.1, 7.9](https://spdx.github.io/spdx-spec/v2.3.1/package-information/#79-package-verification-code-field): verified both | Follows Go's form, hex not base64. Unlike the SPDX code it includes file names, so a rename changes the digest |
| Sorting under the C locale | Reproducible builds: sort file lists with `LC_ALL=C` to avoid locale-dependent order | [reproducible-builds.org, archives](https://reproducible-builds.org/docs/archives/): verified | Follows |
| Binary deliveries identified by hash and licence | Zephyr blobs: each blob in `module.yml` has `path`, `sha256`, `type`, `version`, `license-path`, `url`, `description` and `doc-url`, and Zephyr hosts no blobs in its repositories | [Zephyr modules](https://docs.zephyrproject.org/latest/develop/modules.html) and [binary blobs](https://docs.zephyrproject.org/latest/contribute/bin_blobs.html): verified the field list | Follows in substance. A kit module could declare prebuilt libraries as blobs; not tried |
| Soft-fork commits carry an `Upstream-Status` trailer: `Backport abc123`, `Submitted <link>`, `Inappropriate product-specific` | Yocto: `Upstream-Status:` with `Pending`, `Submitted [where]`, `Backport [version]`, `Denied`, `Inactive-Upstream [...]` or `Inappropriate [reason]`, the reason being only `oe specific` or `upstream ticket <link>`; a CVE fix also carries a `CVE:` tag | [Yocto recipe style guide](https://docs.yoctoproject.org/contributor-guide/recipe-style-guide.html#patch-upstream-status): verified | Differs in form: the guide's values are unbracketed and its `Inappropriate` reason is free text. The guide's form is its own, borrowed from Yocto, not Yocto's exact form |
| Build record, frozen lock and fresh-workspace builds | Reproducible builds: the same source, environment and instructions give bit-identical artefacts, and the producer names the relevant environment attributes. SLSA Build L1 asks for provenance that names the output by digest; L2 adds a hosted build platform and signed provenance | [reproducible-builds.org, definition](https://reproducible-builds.org/docs/definition/) and [SLSA v1.0 requirements](https://slsa.dev/spec/v1.0/requirements): verified | Close to SLSA L1 in substance; the build record is not signed, so not L2 |
| SBOM from `west spdx`, reduced before it goes outward | NTIA published minimum elements for an SBOM | [NTIA minimum elements](https://www.ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom): only the landing page was opened; the list of elements is in a PDF that was not read. **Not verified** | Not compared |
| Zephyr baseline 4.4.2 | Zephyr: a release about every six months; an LTS release every 2.5 to 3 years, maintained for about five years | [Zephyr release process](https://docs.zephyrproject.org/latest/project/release_process.html): verified. How long a regular release is maintained is not stated on that page | See the gaps below |

### Gaps, as recommendations

None of these is adopted, and none changes an existing rule.

1. **Licence enforcement.** The guide says to check the licence of a GPL-only group before enabling it, and nothing checks it. Yocto refuses packages by licence (`INCOMPATIBLE_LICENSE`) and records a checksum of each licence file (`LIC_FILES_CHKSUM`); this was not read on the Yocto pages above and is stated from general knowledge, **not verified**. Recommended: a release check that refuses a lock holding a GPL-only project unless the release record lists an approved exception, and each kit's licence file in its hash list. The check would touch protected code; see [Follow-ups](#follow-ups-that-need-a-protected-path-change).
2. **Kits in the SBOM.** A vendor delivery that is not a Zephyr module, and a kit outside the checkout, appear in no `west spdx` document ([SBOM](product-composition.md#sbom)). Recommended: a release step that adds one SPDX package per kit, with supplier, delivery, the hash-list digest as a checksum and a `LicenseRef-` licence.
3. **Vulnerability information for kits.** A commercial kit has no public advisory feed. Recommended: a named owner per kit who collects the vendor's advisories, and, once the release record's vulnerability check exists, a statement per kit of whether each known issue affects the product.
4. **Long-lived products on a short-lived baseline.** Products live far longer than a regular Zephyr release is maintained. Recommended: prefer an LTS baseline for a product that ships, or record the plan to move off the current one; keep an inventory of maintained kit and fork lines with their planned end dates.
5. **Mirrors and build image.** Recommended: an internal mirror of every public upstream for release builds, and the build container recorded by digest, not by tag.
6. **Vendor-branch commit origin.** Recommended: an `Origin:` trailer on vendor-branch commits that names the delivery and receipt, after Debian's DEP-3 patch header; DEP-3 was **not opened** for this page.

## Open questions

1. Licence inputs in a release build: option A or B of [Licence and identity inputs](#licence-and-identity-inputs).
2. Manifest layering: keep option A, or adopt B, of [Manifest layering](#manifest-layering).
3. A public product with restricted kits: which lock is committed publicly, and how a reader verifies a release without the internal lock.
4. The release manifest extension: the `kits` and `modules` lists, and whether `schema_version` rises with them.
5. Whether a kit module declares prebuilt libraries as Zephyr blobs.

## Follow-ups that need a protected-path change

Not done here. Each needs the owner's approval for that path.

- A `west crux-pins` check, or a separate check under `scripts/`, that every project of a required group is present and active in a release workspace.
- A release bundle checker rule for internal URLs in a public bundle, and the licence refusal of gap 1.
- Wiring the kit module template's tests or a kit-module build into a CI job. The new tests run in the existing Host job's `tests/build` discovery.

## Limits

**What was run**

- `tests/build/test_vendor_kit_template.py`: the hash tool on invented trees, including a comparison with the `find`, `sort` and `sha256sum` (or `shasum -a 256`) pipeline; the CMake function in CMake script mode (`cmake -P`) for the known, unknown, override, release and line cases; and structure checks of this page and the release record.
- `tests/build/test_release_bundle.py`: the schema accepts `vendor/1.1.0` and `work/1.0.1-acme1` and still refuses empty, absolute and dot segments.

**What was not run**

- A Zephyr build of a kit module, the CMake function inside a Zephyr build, or a sysbuild image.
- A real vendor delivery, a real kit repository, a merge with conflicts, a signed tag or a receipt.
- West: the `--active-only` behaviour and the `ZEPHYR_<NAME>_MODULE_DIR` statement were read in source only.
- The restricted-group CI pattern, tokens and fork pull requests.
- Any licence question. Nothing on this page is legal advice.
