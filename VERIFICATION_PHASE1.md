# Phase 1 verification · 11 October 2026

**Phase 1 is built and packaged. Automated editing/rendering tests pass, and the user confirmed that the editor opens from their normal desktop.**

## Passed

- TypeScript check and production Vite build.
- Seven Python tests: edits/mapping, undo/redo, stale and duplicate chat plans, atomic invalid edits, recovery, non-25fps silent input normalization, black/silent timeline gaps.
- React DOM integration against the real Python backend and production JS bundle: selection, split, undo/redo, proposal without mutation, Apply, save/open/history, unsupported-command errors. This is not a visual browser/desktop test.
- Real FFmpeg acceptance: retain source 0–2, 4–6, 8–10 seconds; produce exactly 150 frames / six seconds at 1080p. Seven decoded frame comparisons cover the cut boundaries. Audio pulses start within one frame of the expected seconds.
- Edit during render: stale result discarded. Cancel then rerender: success. Missing media detection and relinking: success.
- A relocated frozen backend runs with PATH restricted to Windows System32: generates/imports demo, previews, exports, saves/opens, and exits cleanly. It does not use developer Python/FFmpeg.
- Bundled filters: ASS Roman-Hinglish captions with bold words, cross dissolve, and 1080×1920 crop. The caption frame was visually inspected. These are compatibility probes, not completed later-phase features.

## Measurements

Intel Core i5-1135G7, 8 logical CPUs, 7.7 GiB RAM, Intel Iris Xe. Rendering uses CPU/libx264.

| Check | Measured | Target |
| --- | ---: | ---: |
| Normalize 12-second generated test clip | 14.11 s | No Phase 1 target |
| Six-second 1080p export | 5.59 s | Correct frames/audio |
| Ten-second 540p preview | 2.55 s | ≤5 s |
| Three-minute 1080p export | 111.08 s | ≤180 s |

These are single-run results on synthetic detailed footage. Real footage and later effects may differ.

## Desktop startup status

Electron 44.7.0 aborts before the app loads because the managed folders' Windows ACLs do not allow its sandboxed processes to read the runtime files. This happened both in a moved workspace folder and a temporary folder. The renderer sandbox remains enabled.

Electron's own [runtime access check](https://github.com/electron/electron/blob/main/shell/browser/win/install_dir_access.cc) explains this error. Automatic approval review initially rejected the runtime-file permission change because it needed explicit authorization. The user then approved it. ALL APPLICATION PACKAGES now has read/execute permission on the existing generated app files only. The grant provides no write access and is not inheritable, so future project/session files do not inherit it. The ACL was read back and confirmed.

Despite that approved fix, launching from the restricted agent process still fails the runtime access check. The user double-clicked the ready executable in their normal desktop session and confirmed: “The editor opens.” Application logs independently show backend-ready, renderer-loaded (packaged), and app-quit events. Electron’s sandbox remains enabled.

The ready artifact is out/Vibeflow-win32-x64/Vibeflow.exe with its sibling runtime files. Normal desktop startup is confirmed. Native video playback and file-dialog interactions remain manual spot-checks because automation is unavailable.

Native desktop automation is also unavailable (“Computer Use native pipe is unavailable”). No browser is connected. Window startup was verified by the user. Detailed layout, native file dialogs, real Chromium video playback and other visible interactions were not automatically verified.

## Evidence and reruns

- verification/report.json — real media, timing and benchmark results.
- verification/packaged-report.json — frozen backend without developer runtimes.
- verification/ui-dom-report.json — React control integration.
- verification/app-startup-report.json — confirmed normal desktop startup.
- verification/app-startup-restricted-report.json — failed launch from the restricted agent process, retained separately.
- verification/Acceptance.vibeflow and Acceptance.media — six-second acceptance project.
- verification/six-second-edit.mp4 — rendered acceptance output.
- .cache/package.log and .cache/forge-final.log — packaging logs.
- .cache/app-startup.log, .cache/app-startup-temp.log and .cache/app-startup-approved.log — exact Windows launch errors before/after the approved grant.

Commands are documented in README.md. The tiny probes and generated media are reproducible with scripts/verify_media.py. Before moving to Phase 2, run the README’s short desktop demo to spot-check native playback, file dialogs and export from the visible app.
