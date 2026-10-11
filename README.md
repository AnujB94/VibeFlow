# Vibeflow — review snapshot

A Windows desktop video editor with a chat panel for proposing edits, recording actions, and applying or undoing changes. Built with Electron, React and a local Python/FFmpeg backend.

**This is the current 0.4.0 prototype for review, not a finished MVP.** The owner reports unreliable workflows and an unintuitive UI. Passing automated tests does not establish that the desktop experience or AI results are good.

## Start from a fresh clone

Use Windows x64. Development used **Node.js 24.18 / npm 11.16** and **Python 3.11.9**. Node and Python must be on PATH: the app starts its backend with the command **python**. macOS/Linux packaging is not supported.

Clone this repository or extract its source ZIP. Open a terminal in the repository folder:

~~~powershell
node --version
python --version
npm ci
npm run setup
npm run dev
~~~

Setup downloads/stages Electron, FFmpeg, ffprobe and fonts. Initial setup needs internet access, a few minutes, and several GB of free space. Premiere is not required.

The repository contains source, requirements and review documents. Executables, downloaded runtimes/models, personal footage and editing sessions are excluded. **runtime/speech/worker.py** is tracked source; the rest of runtime/ is generated.

## First test: no API key or footage needed

1. In the empty **Media** panel, click **Load test clip**. This generates a 12-second video with source frame numbers and an audio pulse each second.
2. Once import finishes, click **Add to timeline** under that item.
3. Click the rectangle labelled **1** on the timeline's **V1** row. Clicking media on the left selects a source for viewing, not its timeline clip for editing.
4. Set **Playhead** to **6.00** seconds. Click **Split**, or send **“Split the selected clip at the playhead”** and click **Apply edit** in chat.
5. Try **Undo** and **Redo**.
6. Click **Refresh preview · 540p**, then use **Sequence** playback. **Source** plays the original working clip and does not show sequence edits.
7. **Save** creates a .vibeflow project. **Export 1080p** creates an MP4.

Preview refresh is explicit; edits do not automatically re-render the monitor.

## Import your own footage

Use **Import video**, then **Add to timeline**. This snapshot accepts **landscape SDR video up to 1920 × 1080**, with each source and the entire sequence limited to **three minutes**. Working copies use 25 fps and linked 48 kHz audio.

HDR, portrait, rotated and larger-than-1080p footage are currently rejected. Start with the generated test clip if a phone video fails. Originals are not overwritten. Keep saved projects and their sibling .media folders together.

## Chat and OpenAI

In **Settings**, enter an OpenAI API key and click **Use key for this session**. The default text model is **gpt-4o-mini** and can be changed. The key stays in backend memory and must be re-entered after restarting. API billing/access is separate from a ChatGPT subscription.

Chat sends the prompt, clip timings and caption text to OpenAI. It does not upload video. API usage is billed to your account.

Send complete instructions, one edit at a time:

- Split the selected clip at the playhead
- Trim selected clip from 1 to 5 seconds
- Move selected clip right
- Remove pauses longer than 1 second
- Add a 12-frame dissolve between clips 1 and 2

Basic explicit split/trim/delete/move phrases work offline. Other wording uses OpenAI. Review the proposed target/range before **Apply edit**, or choose **Discard**. Trim in/out values refer to the source video, not the edited timeline.

**Known limitation:** history is displayed and saved, but previous messages are not sent in the model's planning request. A follow-up such as “confirmed” does not reliably continue a clarification. Repeat the full instruction and inspect the proposal.

## Reproduce a transition

Start with the generated 12-second clip:

1. Select it and split at timeline **6.00s**.
2. Select clip 1. Set **Source in: 0**, **Source out: 5.76**, then **Apply trim**.
3. Select clip 2. Set **Source in: 6.24**, **Source out: 12**, then **Apply trim**.
4. Select clip 1 and open **Effects & captions**.
5. Choose **Cross dissolve**, set **Frames: 12**, and click **Preview transition plan**.
6. Review and **Apply edit** in chat, then refresh the preview.

Those trims leave spare footage on both sides of the cut. Transitions are centred on the cut without changing duration or audio. **Fade through black** is also available. Insufficient spare footage, gaps at the boundary and overlapping transition windows are rejected.

## Pause removal

Open **Effects & captions → Remove pauses & empty gaps**, set the duration/padding/volume threshold, and click **Find pauses**. Review the proposed timeline ranges in chat before **Apply edit**.

The default duration threshold is one second. The generated test clip has shorter pauses; use **0.5s** to demonstrate removal on it.

This detects low-volume audio, not semantic dead space. Quiet speech can be misclassified. Pauses must be strictly longer than the threshold before padding; the default keeps 120 ms around detected speech.

Removal is undoable. Captions follow surviving source ranges and partial cues are flagged. Transitions intersecting removed ranges are removed in the same operation.

## Captions

### Manual captions — offline

Select a timeline clip, open **Effects & captions**, and click **Add manual caption**. Edit text, source-relative timing and comma-separated bold words, then **Save caption**. Size/position use the separate **Apply caption style** button.

Refresh the preview. MP4 exports burn in the text and styling; **Export SRT** provides plain text and timings.

### Automatic captions — OpenAI option

1. Enter an API key in **Settings**.
2. Open **Effects & captions**.
3. Select **OpenAI · uploads timeline audio**.
4. Click **Generate captions**, review the proposal in chat and **Apply edit**.
5. Correct spelling/timing as needed and refresh the preview.

This explicitly uploads timeline audio to OpenAI, then uses the text model for Romanization and keyword suggestions. Hindi words should remain Hindi written in the Roman alphabet, not be translated into English. English words are checked for preservation. Raw recognition text and word timings are retained.

### Optional local recognition

Run **setup-speech.cmd** from the repository folder, or:

~~~powershell
python scripts/setup-speech.py
~~~

This installs faster-whisper and downloads its multilingual base model into runtime/speech/. Restart the app afterwards. Local recognition still uses OpenAI for Roman-Hinglish cleanup and keyword suggestions.

**Known limitation:** caption generation requested through chat always tries local recognition. It does not use the provider selected in the caption controls. If local speech is not installed, use the explicit OpenAI option above. Local installation, speed and transcript quality remain unverified on a second machine.

## Build a portable Windows folder

~~~powershell
python -m pip install --cache-dir .cache/pip -r requirements-build.txt
npm run package
~~~

Open **out/Vibeflow-win32-x64/Vibeflow.exe** and keep the entire folder together. Python/FFmpeg are bundled for editing/rendering. Optional local speech still needs Python for its separate setup.

Close the app before replacing it. Packaging refuses to overwrite an output folder containing **VibeflowData**, **Projects** or **Exports**; preserve that existing folder before rebuilding.

## Debug and test

**Diagnostics** opens backend and FFmpeg logs. Render logs include the command and project revision. For Electron developer tools:

~~~powershell
npm run dev -- --debug
~~~

A packaged app also accepts **Vibeflow.exe --debug**.

From a fresh checkout, run tests in this order:

~~~powershell
npm run build
npm run test:media
npm test
npm run test:ui
python -m scripts.verify_phases
~~~

**test:media** generates fixtures required by the Python render and UI tests, including verification/Acceptance.vibeflow. It also performs a three-minute export benchmark and takes several minutes.

**test:ui** uses a DOM simulation with the real backend; it does not verify native playback, dialogs or layout. After packaging, **npm run test:package** checks a relocated frozen backend. The startup test temporarily relocates the full app, so close it first and use a disposable build.

Generated projects/results live under verification/ and are excluded from Git.

## Known issues and review priorities

- The owner reports confusing controls and unreliable normal use. Review selection, source/sequence playback, preview refresh, caption controls and chat routing.
- The video monitor can be cramped at some window sizes/display scaling settings.
- Chat has no conversation context; “confirmed” can produce an unrelated action.
- Chat captions default to local speech, which is unavailable until optional setup.
- AI interpretation, transcript accuracy, Romanization and keyword quality have not passed a live acceptance suite. Provider tests use stubs; local speech speed/accuracy targets are unmeasured.
- Recovery previously failed when another Windows process held recovery.json. This snapshot includes a separate-snapshot fallback, tested with a real Windows file lock.
- Only one job and one proposed edit are supported at a time. Some network calls delay cancellation.
- Vertical editing, overlays, zooms, music mixing, semantic cleanup and multicamera editing are outside this build.

For review feedback, include exact steps/prompt, expected versus actual behavior, Windows/display scaling, screenshot and the diagnostic error. Do not include API keys or private footage in an issue.

## Code map and requirements

| Path | Role |
| --- | --- |
| src/main.tsx, src/Tools.tsx, src/style.css | Editor, chat, effect/caption controls and layout |
| electron/main.cjs, electron/preload.cjs | Window, native dialogs, IPC and backend process |
| backend/project.py | Project operations, undo, proposals and recovery |
| backend/effects.py, backend/media.py | Validation and shared preview/export renderer |
| backend/analysis.py | Local pause detection |
| backend/provider.py, backend/speech.py | OpenAI planning, recognition and Romanization |
| runtime/speech/worker.py | Optional faster-whisper worker |
| scripts/, tests/ | Setup, packaging, fixtures and regression tests |

See [MVP_PLAN.md](MVP_PLAN.md), [MVP_PLAN_REVIEW.md](MVP_PLAN_REVIEW.md), the [requirements PDF](<Vibeflow — MVP Feature Requirements.pdf>), and [VERIFICATION.md](VERIFICATION.md). Historical verification documents refer to local generated artifacts, not committed files.

The project is marked **UNLICENSED**. Third-party notices and font terms are in [THIRD_PARTY.md](THIRD_PARTY.md) and assets/fonts/LICENSE_DEJAVU.
