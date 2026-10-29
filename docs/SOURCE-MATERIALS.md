# Additional source materials · 2026-10-29

This work supplements the frozen 0.2.1-rc.1 candidate. It does not replace its
tgz, executable versions, hashes, public release, or PR state.

The later local rc.2 candidate includes these notice aggregates and reuses both
2026-10-29 source-material sidecars unchanged. Their rc.1 filenames identify
the source-collection snapshot, not an incompatibility with rc.2; engine versions
and binary hashes are identical across the two candidates.

## Gifski and Rust

The upstream main tree and Cargo.lock remain in the original upstream-sources
sidecar. Additional source archives cover the entire 103-entry lockfile as a
superset: registry archives are checked against Cargo checksums, the git source
is retained at its pinned revision, and the root package is in the main sidecar.
Optional/build/other-platform entries are not asserted to be linked code.

The executable embeds rustc revision `6b00bc3880198600130e1cf62b8f8a93494488cc`,
Rust 1.88.0. Its MIT/Apache and copyright notices are preserved. The binary also
contains an imagequant-4.4.1 reference, consistent with the retained lockfile.
No bit-identical rebuild or complete compiler environment is claimed.

`gif-dispose` omits license files from its crate but declares MIT OR Apache-2.0;
the Apache option and full license text are retained. The two winapi GNU import
library crates use the parent project's dual-license notices, preserved with the
winapi source and their own source headers. Original authorship is not replaced.

## yt-dlp and Python

Python source distributions are checked against hashes in the exact release's
Windows build requirement sets, not merely matched by a current package name.
The collection deliberately includes some build-only and other-platform packages.
Its custom PyInstaller wheel is traced to release `2026.08.19.215425`, upstream
source `70fc17210920bce17f4ab09bbf8104b0dbd45338`, and build recipes
`5eb86b862d61adc3df0f44e6e0b815b7d74fa3f5`; both source trees are retained.

An offline invocation of the pinned yt-dlp executable reports Python 3.14.10,
OpenSSL 3.5.9 and the optional Python-library versions. It simulates a locally
supplied metadata file and never requests its dummy media URL. Raw proxy or
credential diagnostics are not retained. `RELEASE_GIT_HEAD=c91f8de0b...` matches
the generated version.py in the release-tag source; it is not a tag mismatch.

Native mapping additionally preserves the full CPython 3.14.10 source tree and
its build descriptors, curl-impersonate 2.3.0 source/patches, and 17 native
dependency archives. CPython's eight source-dependency branches are resolved
to immutable commits; curl's nine source archives match the CMake recipe's
SHA256 values. They cover OpenSSL 3.5.9, SQLite 3.50.4, libffi 3.4.4
(recipe-derived), curl 8.23.0 and compression/HTTP/TLS dependencies.
The upstream complete notices remain unchanged. Recipe-derived versions are
not mislabeled as independent runtime measurements or a byte-identical native
rebuild. Tk/Tcl is not included because the bundled yt-dlp directory lacks it.

## FFmpeg

The matching build is upstream run `40502414924` from 2026-10-27 at recipe commit
`b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd`. Its main-program build, target-image and
base-image logs are retained with hashes. Actual configure flags are mapped to
build recipes and their dependency groups without executing shell code.

The static map is deliberately conservative and includes platform branches and
build-only components. It is not a linked-code SBOM. `shared` and `version3` are
build flags, not missing external libraries. The matching upstream source cache
is artifact `12733159483`; the approved temporary download is verified against
its published SHA256 before selected archives are streamed out. An initial
HTTP 403 interruption was followed by user authorization to refresh expired
temporary links. Partial/range data is not considered validated source material.
The complete cache SHA256 matched
`d20fbcd32559dab17dc9845660be3510504792a9a748f48a5f78e41be17bc48c`.
All 103 selected native archives were retained; the 2.24 GB outer cache was
removed after extraction. Root/nested Git HEADs and LAME's SVN revision are
checked against the pinned build recipes. Native notices and source inventories
are retained separately from the smaller Cargo/Python source-material sidecar.

The FFmpeg dependencies' three root Cargo.lock files reference 635 registry
entries (including duplicates across locks). Their exact crate archives are
also retained and checked against each lock checksum, even where upstream had
already vendored the source. This remains a conservative superset, not a claim
that every test/platform dependency is linked into the Windows DLLs.

## Reproduction and verification

The maintainer scripts collect evidence and sources without installing or
executing downloaded source code. `vendor/locked-source-materials.json` contains
source URLs, versions, checksums and license-file inventories;
`vendor/runtime-source-evidence.json` binds local executable evidence to binary
hashes; `vendor/ffmpeg-source-map.json` records the conservative recipe map.

`scripts/source_materials.py` builds a separate, deterministic third-party source
sidecar and verifies every retained payload against its embedded inventory.
`--verify <sidecar>` is offline. Main program snapshots remain in the original
upstream-sources sidecar. The small source-material and large native-source
sidecars are separate; all three are needed to review the retained materials.
New artifact names are used instead of overwriting the frozen rc.1 files.

AMF's recipe deliberately removes `.git` and `Thirdparty`. Its 578 retained
files match Git blob hashes from the exact, untruncated commit tree; this is
recorded in `vendor/amf-export-verification.json`, rather than inferred from
an absent HEAD file. LAME's SVN database is queried read-only and the connection
is explicitly closed before temporary-file cleanup.

One earlier inspector run left `.validation/distribution/tmpk9mwyom0/wc.db`
(446,464 bytes) when Windows refused deletion of the still-open database.
Deletion of that path was stopped under the user's instructions. It is not
included in any source sidecar; the user can remove that directory manually.

These records are evidence, not a blanket legal certification. Current blocking
items and any unresolved native-library/source notices remain in DISTRIBUTION.md
and the machine-readable distribution audit. Nothing here authorizes publishing.
