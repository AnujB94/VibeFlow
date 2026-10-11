# Vibeflow plan review

Three independent reviewers examined the original standalone plan:

1. **Requirements:** PDF coverage, chat/history and phase completeness.
2. **Media architecture:** timing, audio, rendering, transitions and packaging.
3. **MVP delivery:** scope, AI feasibility, laptop performance and debugging.

**Verdict:** the architecture is viable and every PDF feature group has a phase. No reviewer found a confirmed framework incompatibility requiring a different stack. The weaknesses were underspecified editing rules and tests that could pass without proving usable automation.

The [revised plan](MVP_PLAN.md) incorporates the corrections below. “Addressed” means the plan now specifies a remedy; it does not mean the standalone implementation or runtime checks have passed.

## P0 — Define before implementation

| ID | Problem and consequence | Correction now in the plan |
| --- | --- | --- |
| P0-1 | **No precise cross-feature edit contract.** “Remap affected timeline elements” did not explain cuts crossing captions, crop keyframes, overlays or transition boundaries. Separate features could work while later cuts corrupt timing. Identified by all three reviews. | Fixed 25 fps/48 kHz working media; half-open ranges and stable source/clip IDs; source/clip and narration anchors; split/trim/drop rules; transition revalidation; composition order. An accumulating mapping fixture checks later cuts, undo and reopen from each relevant phase. |

## P1 — Must pass in the relevant phase

| ID | Problem and consequence | Smallest fix / remaining proof |
| --- | --- | --- |
| P1-1 | **An older or cancelled render could become the current preview.** Revision checks on Apply alone do not protect asynchronous completion. | Jobs capture immutable revisions/settings; validate temporary outputs before publishing; never publish stale output as current; cancel only the job's process and discard partial output. Test edit-during-render and cancel/retry in Phase 1. |
| P1-2 | **A dissolve could shorten the sequence and shift audio/later edits.** The old test checked appearance without asserting duration. | Fixed transition windows around a hard cut, explicit odd-frame allocation and source handles. Preserve video duration and audio timing. Test two transitions, missing handles, total frame count and later cut positions in Phase 2. FFmpeg's xfade also requires compatible input timing/format. [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#xfade) |
| P1-3 | **Packaging could accidentally depend on the development environment.** “No terminal” does not prove bundled executables/fonts work. | PyInstaller onedir; external resources outside ASAR; run from a moved folder with developer Python/FFmpeg absent from PATH. Test bundled media/font probes in Phase 1 and packaged inference when added. [PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html), [Electron ASAR](https://www.electronjs.org/docs/latest/tutorial/asar-archives) |
| P1-4 | **No bounded workload or acceptable wait.** A technically working preview could take minutes after every edit. | Limit the demo to a three-minute 1080p timeline, record laptop specs and establish preview/export/transcription budgets. Initial targets are in the plan and must be measured. Prefer cached short-range previews if needed; do not build a real-time engine. |
| P1-5 | **Manual repairs could conceal failed automation.** Caption, tracking and contextual-selection gates were qualitative. | Preserve raw and corrected outputs separately. Add Roman-Hinglish transcript/code-switch/timestamp thresholds, annotated visibility/centering/loss checks and protected-content/context tests. These are small fixture rubrics, not a large benchmark project. |
| P1-6 | **Face detection does not establish generic object tracking.** The object requirement had no implementation probe and could stall all of Phase 5. | Keep two packaged checkpoints: 5a crops/single-face framing; 5b seeded object tracking/loss handling. Probe OpenCV CSRT on a short clip before integrating 5b; limit it to a selected target and explicit correction after occlusion. [Face Detector](https://developers.google.com/edge/mediapipe/solutions/vision/face_detector/python), [CSRT](https://docs.opencv.org/4.x/d2/da2/classcv_1_1TrackerCSRT.html) |

## P2 — Clarify to avoid unnecessary scope

| ID | Problem | Correction |
| --- | --- | --- |
| P2-1 | **B-roll input and “dead space” were unbounded.** Separate overlay assets and B-roll baked into a flattened edit are different problems; generic editorial judgment can expand indefinitely. | Use separate assets/sections and initially unlabelled candidates for automatic classification. Defer flattened-edit reconstruction. Limit non-silent dead space to annotated failed takes/redundant passages. Define the silence threshold as strictly greater than the duration, before padding. |
| P2-2 | **Phase 1 is relatively large.** The first executable could arrive only after the complete editing surface exists. | Internal packaged checkpoints: 1a import/trim/preview/export, then 1b remaining basic edits/history/undo. Keep seven main phases. |
| P2-3 | **Job IDs alone are insufficient for reproduction.** Changed model versions, sampling or project state can alter a result. | Save revision, prompt/model version, sampled timestamps, proposed/accepted operations, timing and FFmpeg stderr. Add Open diagnostics folder; no telemetry infrastructure. |

## What is still unresolved

- **Measured performance:** the numeric budgets are initial targets, not results. Record the actual laptop hardware and corpus, then measure Phase 1 rendering; measure packaged transcription at the start of Phase 4.
- **Model choice:** select and test a hosted model with the required structured-action and image capabilities. Provider availability, latency and cost are still implementation choices.
- **Automatic quality:** Hinglish recognition, tracking and contextual choices remain empirical gates. Manual fallback keeps the app useful but does not count as a passed automatic requirement.
- **Combined behavior:** extend one short project throughout development. A happy-path final export alone is insufficient; repeat an earlier cut after derived content exists and inspect all timing, then undo/reopen.

The reviews did not justify moving all AI implementation into Phase 1, replacing the chosen stack or adding a general-purpose editing engine. Phase 1 proves the shared foundation; later phases prove their own models and packaged dependencies before integration.

This review changed planning documents only. It did not build or test the standalone editor.
