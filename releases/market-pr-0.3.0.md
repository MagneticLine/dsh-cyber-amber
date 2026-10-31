Add Cyber Amber video download and GIF tools

Adds `MagneticLine/dsh-cyber-amber` under `tools`, providing two tools:

- `amber_download_video`: downloads a video and retains the source file, returning a local path and media metadata.
- `amber_make_gif`: creates a GIF from a video URL or local clip, with configurable dimensions, frame rate, quality and size limit. Size-limited encoding measures Q/L adjustments while preserving dimensions, frame rate, motion quality and clip range.

The entry pins the published v0.3.0 Release tarball for Windows x64. It bundles fixed versions of yt-dlp, FFmpeg/ffprobe and Gifski, and has been validated in an isolated DSH 0.2.1-rc.3 host and an actual desktop session.

Only `data/plugins/MagneticLine__dsh-cyber-amber.yml` is added. Generated READMEs are untouched.
