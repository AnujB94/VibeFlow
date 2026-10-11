> Build update (11 October 2026): cumulative 0.4.0 implements the Phase 2–4 UI/edit/render paths. Automated tests pass. Live OpenAI verification and local speech installation/accuracy/performance gates remain pending. Optional explicit OpenAI audio transcription is provided for the demo. See VERIFICATION.md; this does not mark unmeasured acceptance gates complete.

# Vibeflow — standalone laptop demo plan

Build a small Windows video editor with a preview, a basic timeline and a **chat panel on the right**. Chat retains prompts, proposed edits, applied actions and errors. This replaces the Premiere/UXP plan; the app runs independently of Premiere.

Every phase must produce a runnable packaged app, a saved project and an exported video. All requirements in [the PDF](<Vibeflow — MVP Feature Requirements.pdf>) are included below, with uncertain automation reserved for later phases.

## Architecture and boundaries

- **UI:** Electron + React/TypeScript. Media list, preview, timeline, clip controls and persistent chat. Start with buttons and numeric trims; polished dragging can wait.
- **Processing:** one local Python backend using FFmpeg/ffprobe. The app manages its backend; development mode exposes console output and logs.
- **Project:** versioned JSON containing source ranges, timeline positions, captions, transitions, crop keyframes and chat. Preserve original media/sequence, create edited versions and support undo/redo.
- **Timing:** 25 fps working media, 48 kHz audio and half-open frame ranges `[start, end)`. Keep stable source IDs and separate clip-instance IDs. One frame equals 1,920 audio samples. Validate project revision before Apply; commit each accepted plan atomically and prevent duplicate execution.
- **Preview/export:** share one FFmpeg rendering path. Jobs capture immutable project revisions/settings, write temporary files and publish only validated successful outputs. An old job cannot replace the current preview. Cancel stops that job's FFmpeg process and discards partial output. Keep one render active. Phase 1 disables additional job submissions until the current job finishes or is cancelled; add request coalescing if later automatic refresh needs it. a real-time effects engine is outside the MVP.
- **AI assumption:** use one hosted model connection for natural-language instructions and later visual context, requiring internet/API access. It returns validated edit data, never code. Start transcription locally with faster-whisper and benchmark it. Fully local language/vision models can follow later.
- **Delivery:** portable Windows folder using Electron Forge and PyInstaller **onedir**. Keep backend, FFmpeg runtime and fonts outside Electron's ASAR archive. Pin versions and cache model weights. Logs include job/project revision, prompt/model version, sampled timestamps, proposed/accepted operations, durations and FFmpeg stderr; expose an Open diagnostics folder button.

Limit the demo to a three-minute timeline, landscape SDR footage up to 1920 × 1080, one main video/audio lane, one B-roll overlay lane and captions. Normalize working copies once to 25 fps/48 kHz with zero-based timestamps; retain originals. Use separate main-footage and candidate B-roll assets/sections, initially unlabelled for the automatic test. Reconstructing a flattened edit is deferred. Export landscape 1080p or vertical 1080 × 1920; accounts, multicam, complex effects and unlimited tracks can wait.

## Edit and render rules

- The backend owns the project revision and undo snapshots. A saved project includes media references and chat outcomes; reopening never reapplies an old command. Missing media is reported for relinking.
- Captions/words and crop keyframes retain source/clip anchors. Overlays retain an anchor to narration, plus their own source ranges. Ripple cuts split, trim or drop affected items, then map retained pieces together; split caption cues, flag partially cut words and interpolate crop values at new boundaries.
- Transitions belong to a specific adjacent clip pair. If a cut removes that boundary, remove the transition and report it. If changed clips lose required handles, block that proposed edit until its preview explicitly resolves the conflict.
- Compose in this order: per-clip framing → main-video transitions → framed B-roll overlay → captions in output coordinates. Preview and export use the same ordering and project revision.
- Start one synthetic mapping fixture in Phase 1. As each feature arrives, extend it: make a cut after captions/transitions/crops/overlays exist, then check timing, undo and save/reopen. This catches interactions before the final demo.

## Phase 1 — Basic editor and export

- **1a:** package import/play/seek, numeric trims, preview and export first. Keep video/audio linked.
- **1b:** add split, reorder, delete/ripple controls and complete the project/history workflow below. Both checkpoints must run as portable apps.
- Save/reopen and undo/redo. Add the right-side chat/history with a few explicit commands, such as “Split the selected clip at the playhead.”
- Prove packaged startup/shutdown from a different folder with developer Python/FFmpeg absent from PATH. Verify the bundled runtime/fonts, media relinking, edit-during-render and cancel-then-rerender.
- Run tiny rendering probes for transitions, bold Roman-Hindi/English text and vertical crops to expose missing filters/fonts early.

**Pass:** launch the portable app without developer terminals. From the frame-counter/audio-pulse test clip, retain source ranges 0–2, 4–6 and 8–10 seconds; export six seconds with correct boundaries and audio sync. Undo, save/reopen and check history. This phase is already a usable manual editor.

## Phase 2 — Natural-language edits and transitions

- Interpret varied wording for supported actions. Show affected clips/ranges before Apply; clarify ambiguous scope.
- Find hard cuts from adjacent clips. Support cross dissolve and fade through black with explicit type, frame duration and placement.
- Add transitions only when requested. A D-frame transition occupies floor(D/2) frames before the cut and ceil(D/2) after it, using source handles. Reject missing handles/overlapping transition windows. Preserve total duration, audio and all other hard cuts.
- Record actual outcomes in chat; manual editing remains available when the model is unavailable.

**Pass:** test two transitions, an odd duration and insufficient handles. Total frame count, later cut positions and audio pulses must stay unchanged. Test another type, a paraphrase and an ambiguous request, then undo. Only requested boundaries change.

## Phase 3 — Pause, silence and gap removal

- Detect pauses/silences and empty timeline gaps. A pause qualifies strictly above the requested threshold, measured before speech padding; test below, exactly at and above one second.
- “Remove all pauses longer than one second” previews ranges, then automatically applies approved cuts to an edited sequence version.
- Preserve clip order/audio sync and remap affected timeline elements. Invalidate obsolete analyses/previews after changes. Contextual non-silent dead space follows in Phase 7.

**Pass:** use measured pauses above/below one second. Remove only qualifying ranges, avoid clipping words and compare original/edited playback and exports. Verify planned boundaries within one frame, undo and reopen.

## Phase 4 — Editable Hinglish captions

- Transcribe mixed Hindi-English speech with timestamps. The default is Roman Hinglish: Hindi words written in Latin letters alongside unchanged spoken English words (for example, “Aaj hum video edit karenge”). Transliterate Hindi when needed; do not translate it into English.
- Insert editable caption items automatically. Allow text/timing corrections, position/size changes and individual bold keywords from chat or manual selection.
- Keep editable captions in project JSON; use styled ASS and Latin fonts for preview/export. SRT is an additional plain-text output.
- First benchmark raw recognition/timing and run packaged CPU inference on a short reference clip. Choose the smallest model meeting the acceptance rubric below; download/cache it before the live demo. The model proposes bold keywords, which remain editable.

**Pass:** “Add Hinglish captions with bold keywords” inserts captions. Compare the initial transcript with a reference, edit a word/time/style and verify the saved project and export. Make another cut and check caption remapping. An SRT file alone does not satisfy this phase.

## Phase 5 — Vertical conversion and subject tracking

- **5a:** package a 1080 × 1920 sequence version with editable position/scale/crop keyframes and automatic single-face framing.
- **5b:** first prove a seeded OpenCV CSRT tracker on a short object clip; then package object tracking and lost-target handling. Face detection alone does not satisfy this checkpoint. Limit the demo to one chosen visible target; flag occlusion for correction. Smooth movement and reset at shot boundaries.
- “Keep the speaker centered” adjusts framing across clips. Clarify multiple subjects, flag lost tracking and allow corrections. Reposition captions for vertical output.

**Pass:** export a moving speaker, a differently framed second shot and an object shot. Check dimensions, subject visibility, smooth framing, captions and saved edits. Manual cropping alone does not prove automatic tracking.

## Phase 6 — B-roll review and controlled trimming

- Add the B-roll overlay lane and let the editor identify B-roll. Flag sections whose actual timeline duration exceeds two minutes.
- Use sampled visual similarity/shot boundaries to flag possible repetition and present keep ranges.
- “Shorten all B-roll sections to 5–8 seconds” applies editor-reviewed excerpts.
- Retain their relationship to the narration. Removed overlay portions reveal the main footage; they must not shorten or shift its audio.

**Pass:** reduce a B-roll section over two minutes to a reviewed seven-second excerpt while retaining important content and narration sync. A long source used for only five seconds must not be flagged as a long timeline section.

## Phase 7 — Contextual B-roll and dead-space decisions

- Automatically propose B-roll classifications/sections from sampled frames, shots and narration, without relying solely on manual labels.
- Select relevant 5–8 second excerpts using visual content, repetition and transcript context. Explain choices and preserve key moments.
- Limit non-silent dead-space suggestions to annotated failed takes or redundant repeated passages. Quiet audio or low motion alone must not mean “unnecessary”; open-ended editorial judgment is deferred.
- Apply approved suggestions using the existing timeline operations and mappings.

**Pass:** compare suggestions on initially unlabelled footage with a small annotated reference, including repetitive content and an important moment that must remain. Then demonstrate cuts, captions, B-roll, an explicitly requested transition and vertical framing together in one export.

This is the highest-uncertainty phase. Poor contextual choices fail its acceptance test; the earlier editor remains usable while the model/prompt improves.

## PDF coverage

| Requirement | Demonstrated in |
| --- | --- |
| Natural-language timeline instructions | Phase 2, extended with each feature |
| Pauses, silences, gaps; preserve original and order | Phase 3; contextual non-silent dead space in Phase 7 |
| Hinglish, timestamps, editable captions/style, bold keywords | Phase 4 |
| Explicit transition type, duration and placement | Phase 2 |
| 1080 × 1920, faces/objects, changing framing | Phase 5 |
| B-roll over two minutes, repetition, contextual trims and sync | Phase 6 foundations; automatic/contextual completion in Phase 7 |

All seven tests must pass before claiming PDF coverage on the agreed demo footage. Manual fallback keeps the app useful but does not replace an automatic feature's acceptance test.

## Measurable demo gates

Record CPU/RAM/GPU and freeze the reference clips in Phase 1. The following are initial acceptance targets, not measured results; revise them explicitly after laptop measurements if needed, rather than silently calling a slow or inaccurate demo complete.

| Gate | Target and when to measure |
| --- | --- |
| Preview/export speed | In Phase 1: a 10-second 540p preview refresh within 5 seconds; a three-minute 1080p basic export within 3 minutes. If full preview refresh is slow, render only the selected range and reuse cached results. Re-measure when effects arrive. |
| Transcription speed | At the start of Phase 4: process a 60-second Hinglish clip within 2 minutes on the chosen local configuration; record peak RAM and warm/cold times. |
| Raw captions | On that reference: normalized word error rate ≤15% against an agreed Roman-Hinglish reference (with accepted spelling variants), all annotated Hindi/English code-switch keywords retained without translation, and ≥95% of cue boundaries within 200 ms. Evaluate before corrections and save both raw/corrected results. |
| Automatic framing | On annotated visible-target samples: target region remains visible in ≥95%; speaker centre stays in the middle third in ≥95%. Flag every annotated lost-target interval; evaluate before manual framing repairs. |
| Contextual suggestions | Use five B-roll positives and two main-footage negatives: classify at least four positives correctly, preserve both negatives and every annotated must-keep moment. Retained excerpts total 5–8 seconds per requested B-roll section, stay in source order and align with narration. Include one redundant-passage positive and one important-passage negative; both decisions must match the reference. |
| Failures/integration | Missing media, offline API, malformed AI plan, stale revision and cancelled render must cause clear outcomes without partial edits or published partial files. Every new phase exports the accumulated fixture, including a later cut, undo and reopen. |

Check hosted-model connectivity and cache local weights before demonstrations. API failure leaves manual editing available; fixed commands do not count as full natural-language coverage.

At every phase: package, replay previous demo steps, save/reopen, exercise a failed/cancelled job and inspect the export. Retain a working checkpoint. Use one demo folder containing a frame/audio test clip, Hinglish speech, moving subjects/objects and more than two minutes of B-roll.

## Existing work

The old UXP prototype and its build artifacts were removed. Phase 1 now has a standalone Electron/React interface, a local Python/FFmpeg backend, a portable Windows package, and automated editing/media/DOM tests. The six-second frame/audio acceptance export and initial speed targets pass. The frozen backend also passes from a relocated folder without developer runtimes on PATH. A runtime-file permission issue was fixed after explicit user approval. The restricted agent process still cannot launch Electron, but the user confirmed the normal desktop launch; app logs show both backend and renderer loading. Manual playback/file-dialog checks remain before final phase acceptance. See [VERIFICATION.md](VERIFICATION.md).

Technical references: [Electron packaging](https://www.electronjs.org/docs/latest/tutorial/distribution-overview), [ASAR limitations](https://www.electronjs.org/docs/latest/tutorial/asar-archives), [PyInstaller bundles](https://pyinstaller.org/en/stable/operating-mode.html), [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [MediaPipe face detection](https://developers.google.com/edge/mediapipe/solutions/vision/face_detector/python), [OpenCV CSRT](https://docs.opencv.org/4.x/d2/da2/classcv_1_1TrackerCSRT.html). Model accuracy and laptop performance require the phase tests above. See [the tiered review](MVP_PLAN_REVIEW.md) for findings and remaining validation.
