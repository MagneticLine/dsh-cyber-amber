# Distribution evidence and public-release gate

The 0.2.1-rc.1 package is a local functional validation candidate. It is **not
cleared for a new public distribution**. Main project source snapshots and license
files are present, but they do not prove complete corresponding-source coverage
for every library inside the upstream binaries.

`vendor/distribution-audit.json` is a machine-readable evidence inventory, not a
complete SBOM or a legal certification. It binds the main source snapshots to
their recorded checksums, lists the Gifski lock entries, preserves FFmpeg build
recipe references, and indexes yt-dlp's third-party notices. Optional, build-only
or other-platform entries are not asserted to be shipped dependencies.

## Progress · 2026-10-29

DIST-01 through DIST-03 now have retained source/notice evidence, checked using
the three source sidecars. The small additional sidecar preserves the 102
Gifski Cargo dependency sources (the root entry is already in the main sidecar),
519 further registry sources from native dependency locks, 21 Python source packages,
custom PyInstaller source/build recipes, curl-impersonate and CPython source,
18 Python/native source records, and Rust license/copyright records. Registry source hashes
are matched to the original Cargo/Python requirement locks. This is a deliberate
superset including optional/build/other-platform packages, not a linked-code SBOM.

The native sidecar retains 103 archives from the exact FFmpeg build's source
cache, matching upstream artifact SHA256. The inspector checks root and nested
Git commits, LAME SVN revision 7113, and AMF's 578-file exported tree. Native
notices, build logs and API evidence accompany the archives. The 2.24 GB outer
download cache was removed after verified extraction.

Details and evidence scope: [SOURCE-MATERIALS.md](SOURCE-MATERIALS.md).
`SOURCE_MATERIAL_NOTICES.txt` and the additional sidecar are new local materials;
the frozen rc.1 tgz has not been replaced. A later candidate must include the
new notices before any new public binary distribution is considered.

## Remaining packaging step

| ID | Component | Evidence still needed before public release |
|---|---|---|
| DIST-04 | Candidate package | The frozen rc.1 tgz predates the additional notices. Prepare a new candidate containing them, verify the actual package, then obtain user review before any public action. |

This list describes verification gaps, not a conclusion that upstream releases
or this package violate a license. Do not mark these items resolved merely because
the encoders work, a license text is included, or an upstream project URL exists.
Do not relicense the plugin aggregate as a shortcut. Original glue remains MIT;
each independent program and library keeps its own terms.

## Repeatable checks

Run `python scripts/audit-distribution.py --sidecar <main-source-sidecar> --materials-sidecar <additional-source-sidecar> --native-sidecar <native-source-sidecar>` to compare
the retained evidence with the exact archived inputs. `--write` is an explicit
maintainer operation after inspecting changed evidence. `--require-public-ready`
fails while any public-release blocker remains. Candidate packaging reports the
blockers but does not hide them or call the package publication-ready. Downloaded
ranges were accepted only after matching the complete upstream artifact digest.

The review scope is retained material and version evidence. A complete linked-code
SBOM, bit-identical rebuild, and legal certification are not claimed. The native
source sidecar is large (about 2.1 GB); it is not part of the npm installation.

Sources remain a separate sidecar, not duplicated inside the installable tgz.
The fixed bundled-engine design is retained. Any eventual binary substitution,
public upload, maintainer contact or PR requires the user's separate review.

References: [FFmpeg legal information](https://ffmpeg.org/legal.html),
[Gifski license](https://github.com/ImageOptim/gifski/blob/1.34.0/LICENSE),
[yt-dlp licensing](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/README.md#licensing).
