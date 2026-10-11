# Bundled runtime notices

This local demo bundles Electron (MIT and Chromium notices in the app folder), a PyInstaller Python runtime, FFmpeg/ffprobe, and DejaVu Sans fonts.

- FFmpeg 6.1.1 essentials build from Gyan, obtained through pinned ffmpeg-static 5.3.0. GPL build with libx264 and libass. License and upstream build/source information are under resources/media/FFMPEG-LICENSE.txt and FFMPEG-README.txt. Upstream: https://www.gyan.dev/ffmpeg/builds/ and https://ffmpeg.org/.
- ffprobe from @ffprobe-installer/win32-x64 5.1.0 (Gyan build); GPL-3.0, upstream information under resources/media/FFPROBE-README.md.
- DejaVu Sans regular/bold: the full font license is under resources/media/fonts/LICENSE_DEJAVU and assets/fonts/LICENSE_DEJAVU.
- Electron's LICENSE and LICENSES.chromium.html ship beside Vibeflow.exe.
- Python and PyInstaller license notices ship with the frozen runtime where supplied by those tools.

This is a private laptop demonstration build, not a signed public distribution. Preserve upstream notices and review distribution obligations before public release.
