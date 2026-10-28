# External tools and references

This package contains original JavaScript glue and tests. It does not bundle FFmpeg,
Gifski, yt-dlp, a Python interpreter, or another plugin's credentials/runtime.

- Gifski: <https://github.com/ImageOptim/gifski>, AGPL-3.0-or-later; alternative
  commercial licensing is offered by its author. Tested engine version: 1.34.0.
- FFmpeg / ffprobe: <https://ffmpeg.org>. The license depends on build options;
  consult the distribution you install. No FFmpeg binary is distributed here.
- yt-dlp: <https://github.com/yt-dlp/yt-dlp>. Source is Unlicense; standalone
  distributions can include third-party code under additional licenses.
- DeepSeek Harness host API: <https://github.com/deepseek-ai/deepseek-harness>.
  Host packages are supplied by DSH, not installed or redistributed by this bundle.

Design references, not runtime dependencies:
<https://github.com/tkwkeven/dsh-ytdlp>,
<https://github.com/STARDUSTLC666/dsh-ffmpeg>, and
the user's local DSH development guide. The download/encode pipeline was informed
by earlier project-owned NoneBot integration experiments and implemented here using
the DSH managed subprocess API.
