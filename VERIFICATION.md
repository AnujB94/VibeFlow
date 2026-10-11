# Phase 2–4 build verification · 11 October 2026

This is a cumulative 0.4.0 demo with independent manual controls for transitions, silence removal and captions. Phase 1 is preserved beside it. Live OpenAI and local speech accuracy/performance gates are pending; do not label these phases fully accepted until those checks pass.

## Passed in this build

- Production TypeScript/Vite build.
- 14 Python regression tests at the initial Phase 2–4 build, with ResourceWarnings treated as errors; 15 tests passed after the recovery fix.
- Cross dissolve and fade-through-black actual FFmpeg renders, including a 13-frame odd-length window centred on the cut.
- Exact 100-frame / four-second output with effects. Decoded audio PCM is identical to the hard-cut baseline for both transitions.
- Decoded centre frame of the black transition is black; a frame outside the transition is unchanged within compression tolerance.
- ASS caption burn-in with Roman Hindi and an individually bold word; caption frame visually inspected.
- Strict silence threshold checks below, exactly at, and above one second, with padding rounded inward.
- Caption source anchors split/trim with subsequent cuts, flag partial cues, and survive save/reopen and undo.
- Invalid ranges, invalid script, insufficient source handles and overlapping transition windows rejected without mutation.
- Proposal Apply is atomic; expired and duplicate proposals cannot execute twice.
- OpenAI structured transport tested with stub responses: store:false, no key in payload/project state, English-word preservation.
- Production React DOM with the real backend: selection/edit/undo/redo, preview before Apply, save/reopen/history, missing-key error, manual caption creation/editing, password settings input.
- Earlier Phase 1 rendering and project regression tests remain green.
- Cumulative 1080p render with two transitions and captions; real pause-analysis job finds six intervals, atomically reduces 150 frames to 48, renders, and undoes back to 150. Transitions touched by the removed ranges are removed with the same undoable operation.
- Relocated frozen backend with PATH restricted to Windows System32 generates/imports footage, previews and exports a transition plus captions, saves/reopens and shuts down successfully.

- Recovery fix: a locked canonical recovery file falls back to a complete separate snapshot. Regression coverage and a real Windows file-lock test against the frozen backend passed.

## Pending acceptance gates

- The agent has not run a live OpenAI acceptance suite: chat paraphrase/clarification quality, real transcription, Romanization and keyword quality remain unverified.
- Restricted-session network policy blocked pip downloads. Local speech setup and worker are included, but dependencies/model are not bundled or installed. Local inference requires running setup-speech.cmd from a normal desktop session first.
- No human-checked Hinglish reference recording is available. Raw WER, bilingual keyword preservation, 95% word-boundary timing within 200 ms, and 60-second transcription in two minutes remain unmeasured.
- Updated native Electron layout/playback/dialog interactions need a normal desktop spot-check. The previous Phase 1 build opened successfully on this user's desktop; restricted agent launching remains unavailable.
- Phase 1 export speed measurements do not establish performance with multiple transitions or speech recognition.

## Evidence

- verification/phase4/service-report.json — cumulative 1080p and actual pause-job checks.
- verification/packaged-report.json — relocated frozen backend checks.
- verification/phase4/Phase4Demo.vibeflow — ready-to-open demo project (keep its .media folder).
- verification/phase4/report.json — real render/audio checks.
- verification/phase4/caption-frame.png — visually inspected caption output.
- verification/phase4/dissolve.mp4 and black.mp4 — four-second effect renders.
- verification/ui-dom-report.json — current React/backend control checks.
- .cache/phase-tests.log — full test result.
- .cache/ui-phase4.log — UI integration output.
- .cache/package-phase4.log — build/package output.
- VERIFICATION_PHASE1.md — earlier phase's complete evidence and hardware timings.

API implementation references: [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses), [speech transcription](https://developers.openai.com/api/docs/guides/speech-to-text), [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
