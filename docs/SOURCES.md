# Source code and build information

Version 0.2.1 has a separate source sidecar named
`dsh-cyber-amber-0.2.1-upstream-sources.tar.gz`, prepared locally for release review.
The main source revisions below are unchanged. Additional source and notice
materials are documented in [SOURCE-MATERIALS.md](SOURCE-MATERIALS.md).
The frozen rc.1 installation package predates these new notices. The rc.2 and 0.2.1
package includes them and reuses the unchanged 2026-10-29 additional source
sidecars; see [DISTRIBUTION.md](DISTRIBUTION.md). User approval is still required.

Cyber Amber does not modify the bundled executables or DLLs. It copies selected
files from the upstream distributions identified by `vendor/sources.lock.json`.
Original plugin code is MIT; this does not relicense the independent programs.
License texts and upstream attribution remain under `vendor/licenses/`.

The same [v0.2.0 release](https://github.com/MagneticLine/dsh-cyber-amber/releases/tag/v0.2.0)
that hosts the binary plugin offers `dsh-cyber-amber-0.2.0-upstream-sources.tar.gz`.
It preserves the exact main-project source trees and build recipes listed below,
with a SHA256 inventory. These snapshots are source material, not an installable
DSH plugin. Upstream dependency sources are available through the linked lockfiles,
package source records and recipes; the snapshots are not a claim that a complete
offline build environment or every dependency archive has been vendored.

## Gifski 1.34.0

- [Exact source tree](https://github.com/ImageOptim/gifski/tree/1060eab4500a20f27e2fa3ab7e85473d0e921cbd)
- [Source archive](https://github.com/ImageOptim/gifski/archive/1060eab4500a20f27e2fa3ab7e85473d0e921cbd.tar.gz)
- [Cargo manifest](https://github.com/ImageOptim/gifski/blob/1060eab4500a20f27e2fa3ab7e85473d0e921cbd/Cargo.toml),
  [dependency lockfile](https://github.com/ImageOptim/gifski/blob/1060eab4500a20f27e2fa3ab7e85473d0e921cbd/Cargo.lock),
  [build documentation](https://github.com/ImageOptim/gifski/tree/1060eab4500a20f27e2fa3ab7e85473d0e921cbd#readme)
- License: AGPL-3.0-or-later, including the separate dependency notices in the source tree.

With the upstream Rust toolchain and a Windows x64 target, the documented CLI build
is `cargo build --release --locked`. Cargo obtains dependency source using the
versions and checksums in the lockfile; `cargo vendor --locked` can preserve it for
an offline rebuild. Consult the manifest for upstream feature choices. We ship
the unchanged upstream executable; this project does not claim a bit-identical
local rebuild of the upstream release.

## FFmpeg / ffprobe and libav DLLs

- Version: `n9.0.2-36-g6882969ce9`, LGPL shared build, built 2026-10-27.
- [Exact FFmpeg source](https://github.com/FFmpeg/FFmpeg/tree/6882969ce9fd2aa6aa1d0008b2bfe1c838aac11d)
- [FFmpeg source archive](https://github.com/FFmpeg/FFmpeg/archive/6882969ce9fd2aa6aa1d0008b2bfe1c838aac11d.tar.gz)
- [BtbN build scripts, patches and dependency records](https://github.com/BtbN/FFmpeg-Builds/tree/b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd)
- [Dependency source URLs and revisions](https://github.com/BtbN/FFmpeg-Builds/tree/b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd/scripts.d)
- [Build instructions](https://github.com/BtbN/FFmpeg-Builds/blob/b4a2b1d7cc241786eb8e2b588a7ade40cad48bbd/README.md)
- [Actual bundled configuration](../vendor/ffmpeg-buildconf.txt)

The corresponding build variant is `win64 lgpl-shared 9.0`. The upstream Docker
build scripts include dependency download recipes and patches; see `download.sh`
and `scripts.d/` to obtain the dependency source trees, not just FFmpeg's tree.
Some dependencies have their own licenses in addition to FFmpeg's LGPLv3+.
The DLLs are shipped separately and may be replaced along with matching executables.
Set the plugin's `ffmpegPath` and `ffprobePath` to use your own modified build;
do not mix incompatible DLL versions in the bundled directory.

## yt-dlp 2026.10.26 directory distribution

- [Exact source tree](https://github.com/yt-dlp/yt-dlp/tree/f264a6cbd1f630894da0f368df00f8aae50140e0)
- [Source archive](https://github.com/yt-dlp/yt-dlp/archive/f264a6cbd1f630894da0f368df00f8aae50140e0.tar.gz)
- [Windows build workflow](https://github.com/yt-dlp/yt-dlp/tree/f264a6cbd1f630894da0f368df00f8aae50140e0/.github/workflows)
- [Bundler and pinned dependencies](https://github.com/yt-dlp/yt-dlp/tree/f264a6cbd1f630894da0f368df00f8aae50140e0/bundle)
- [Complete upstream third-party notices and source access directions](../vendor/licenses/yt-dlp-THIRD_PARTY_LICENSES.txt)

The upstream source is Unlicense; the official PyInstaller binary distribution
contains GPLv3+ components and private Python dependencies under their own terms.
Preserve the entire `_internal` directory. The upstream source records, build
requirements and third-party notices identify the original dependency projects.
Use the source versions from that release rather than current development heads.

## Access and replacement

Downloads do not require a commercial account. The plugin does not prevent using
modified programs: the four explicit executable-path settings bypass the bundled
selection. To rebuild Cyber Amber's package, follow `vendor/README.md`; it does not
compile the external programs or change their source code.

If an upstream source URL becomes unavailable, open an issue on this repository
with the component, version and release filename so its source access can be
restored. The release snapshots preserve the named main trees and build recipes
even if an upstream binary autobuild expires. Do not assume a newer upstream
release is equivalent to the version whose binary hash is in our manifest.
