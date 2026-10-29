# External tools and references

The original JavaScript glue and tests are MIT licensed. The Windows x64 release
is an aggregate of that code and the following separately licensed command-line
programs. Their upstream notices and license texts are preserved under `vendor/licenses`.
Additional dependency notices and authorship are preserved in
`vendor/SOURCE_MATERIAL_NOTICES.txt` and `vendor/NATIVE_SOURCE_NOTICES.txt`.
These are conservative collections; inclusion does not assert every optional,
build-only or other-platform dependency is linked into the Windows binaries.
No other plugin's credentials or runtime are included.
Corresponding-source access directions, upstream dependency records and build
instructions are collected in `docs/SOURCES.md`. Release downloads also offer
immutable upstream source snapshots separately from the installable tgz.
Versions 0.2.1-rc.2 and 0.2.1 additionally use the two unchanged, locally retained
2026-10-29 source-material sidecars described in `docs/SOURCE-MATERIALS.md`.
The multi-gigabyte source archives are not installed as runtime dependencies.

- Gifski: <https://github.com/ImageOptim/gifski>, AGPL-3.0-or-later; alternative
  commercial licensing is offered by its author. Tested engine version: 1.34.0.
- FFmpeg / ffprobe n9.0.2-36-g6882969ce9, BtbN LGPL shared build, plus its libav
  DLLs. See `vendor/licenses/ffmpeg-LICENSE.txt` and `GPL-3.0.txt`.
  Exact FFmpeg source: <https://github.com/FFmpeg/FFmpeg/tree/6882969ce9>.
  Build recipes: <https://github.com/BtbN/FFmpeg-Builds/tree/autobuild-2026-10-27-18-38>.
- yt-dlp 2026.10.26, official Windows x64 onedir distribution. It includes a
  private Python runtime and bundled third-party components; a separate Python
  installation is not needed. The yt-dlp source is Unlicense; the binary aggregate
  is subject to the included third-party terms, including GPLv3+.
  Full upstream notices: `vendor/licenses/yt-dlp-THIRD_PARTY_LICENSES.txt`.
  Exact source: <https://github.com/yt-dlp/yt-dlp/tree/2026.10.26>.
- DeepSeek Harness host API: <https://github.com/deepseek-ai/deepseek-harness>.
  Host packages are supplied by DSH, not installed or redistributed by this bundle.

`vendor/sources.lock.json` records release origins, source/build references and
archive checksums; `vendor/manifest.json` records every bundled dependency file's
size and SHA256. Updates are manual release decisions, never automatic. Users may
explicitly select their own executable paths, including modified versions.

Design references, not runtime dependencies:
<https://github.com/tkwkeven/dsh-ytdlp>,
<https://github.com/STARDUSTLC666/dsh-ffmpeg>, and
the user's local DSH development guide. The download/encode pipeline was informed
by earlier project-owned NoneBot integration experiments and implemented here using
the DSH managed subprocess API.
