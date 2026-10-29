Add Cyber Amber video download and GIF tools

This adds one entry for `MagneticLine/dsh-cyber-amber` in the tools category.
It provides `amber_download_video` and `amber_make_gif`, including measured GIF
size-limit handling through Q/L adjustments.

The entry pins the GitHub Release tarball for v0.2.1. The self-contained package
supports Windows x64 and was tested with DSH 0.2.1-rc.3. Other platforms and host
versions are not claimed. It bundles fixed engines; no install-time engine
download or automatic update is performed.

Validation covers both tools in an isolated DSH profile, parameter validation,
GIF decoding, size-limit failure, cancellation and cleanup. A user also verified
Bilibili download and GIF creation in their actual DSH session using rc.2,
whose runtime implementation and dependency hashes match 0.2.1.

Only `data/plugins/MagneticLine__dsh-cyber-amber.yml` is proposed. Generated
READMEs and other entries are unchanged.
