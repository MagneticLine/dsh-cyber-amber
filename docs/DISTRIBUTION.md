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

## Blocking items

| ID | Component | Evidence still needed before public release |
|---|---|---|
| DIST-01 | FFmpeg / libav DLLs | Match all actually included libraries to exact versions, source/patches, licenses and retained notices. Build recipes with moving revisions are insufficient by themselves. |
| DIST-02 | Gifski | Confirm shipped build features and linked dependencies; close their source and notice mapping against the retained Cargo.lock and source tree. |
| DIST-03 | yt-dlp directory distribution | Identify exact private Python/native dependency versions and source coverage. Its cross-platform notice list alone does not establish this Windows inventory. |

This list describes verification gaps, not a conclusion that upstream releases
or this package violate a license. Do not mark these items resolved merely because
the encoders work, a license text is included, or an upstream project URL exists.
Do not relicense the plugin aggregate as a shortcut. Original glue remains MIT;
each independent program and library keeps its own terms.

## Repeatable checks

Run `python scripts/audit-distribution.py --sidecar <source-sidecar>` to compare
the retained evidence with the exact archived inputs. `--write` is an explicit
maintainer operation after inspecting changed evidence. `--require-public-ready`
fails while any public-release blocker remains. Candidate packaging reports the
blockers but does not hide them or call the package publication-ready.

Sources remain a separate sidecar, not duplicated inside the installable tgz.
The fixed bundled-engine design is retained. Any eventual binary substitution,
public upload, maintainer contact or PR requires the user's separate review.

References: [FFmpeg legal information](https://ffmpeg.org/legal.html),
[Gifski license](https://github.com/ImageOptim/gifski/blob/1.34.0/LICENSE),
[yt-dlp licensing](https://github.com/yt-dlp/yt-dlp/blob/2026.10.26/README.md#licensing).
