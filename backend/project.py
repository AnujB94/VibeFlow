"""Frame-based project editing. The backend is the sole owner of project revisions."""
import copy
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid

FPS, RATE, MAX_FRAMES = 25, 48000, 4500

def ident():
    return uuid.uuid4().hex

def clone(value):
    return copy.deepcopy(value)

def frame(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("Use a whole frame number.")
    return value

def duration(project):
    return max((c["start"] + c["out"] - c["in"] for c in project["clips"]), default=0)

def validate(project):
    if project.get("schema") not in (1, 2) or project.get("fps") != FPS:
        raise ValueError("This project format is not supported.")
    media = {m["id"]: m for m in project["media"]}
    if len(media) != len(project["media"]):
        raise ValueError("Duplicate media IDs.")
    seen, end = set(), 0
    for clip in sorted(project["clips"], key=lambda c: c["start"]):
        if clip["id"] in seen or clip["source"] not in media:
            raise ValueError("Invalid clip reference.")
        seen.add(clip["id"])
        a, b, start = (frame(clip[k]) for k in ("in", "out", "start"))
        if a < 0 or b <= a or b > media[clip["source"]]["frames"] or start < end:
            raise ValueError("Clips overlap or use unavailable source frames.")
        end = start + b - a
    if end > MAX_FRAMES:
        raise ValueError("Phase 1 supports timelines up to three minutes.")
    from backend.effects import validate_effects
    validate_effects(project)
    if any(project.get(k) for k in ("overlays", "crops")):
        raise ValueError("This build does not support overlays or crops.")

def source_mapping(project):
    return [{"clip": c["id"], "source": c["source"], "source_start": c["in"],
             "source_end": c["out"], "timeline_start": c["start"],
             "timeline_end": c["start"] + c["out"] - c["in"]}
            for c in sorted(project["clips"], key=lambda c: c["start"])]

def map_source_range(project, source, start, end):
    output = []
    for row in source_mapping(project):
        if row["source"] != source:
            continue
        a, b = max(start, row["source_start"]), min(end, row["source_end"])
        if a < b:
            output.append({"clip": row["clip"], "source_start": a, "source_end": b,
                           "start": row["timeline_start"] + a - row["source_start"],
                           "end": row["timeline_start"] + b - row["source_start"]})
    return output

def operate(project, operation):
    from backend.effects import special, remap
    effect = special(project, operation)
    if effect:
        validate(effect[0])
        return effect
    result = clone(project)
    clips = result["clips"]
    kind = operation.get("type")
    target = next((c for c in clips if c["id"] == operation.get("clip")), None)
    if kind == "append":
        media = next((m for m in result["media"] if m["id"] == operation.get("source")), None)
        if not media:
            raise ValueError("Select imported media first.")
        clips.append({"id": ident(), "source": media["id"], "in": 0,
                      "out": media["frames"], "start": duration(result)})
        label = "Added " + media["name"] + " to the timeline."
    else:
        if not target:
            raise ValueError("Select a timeline clip first.")
        old_end = target["start"] + target["out"] - target["in"]
        if kind == "split":
            point = frame(operation["at"])
            if not target["start"] < point < old_end:
                raise ValueError("Place the playhead inside the selected clip.")
            split_source = target["in"] + point - target["start"]
            right = {**target, "id": ident(), "_parent": target["id"], "in": split_source, "start": point}
            target["out"] = split_source
            clips.append(right)
            label = f"Split the selected clip at {point / FPS:.2f}s."
        elif kind == "trim":
            a, b = frame(operation["in"]), frame(operation["out"])
            delta = (b - a) - (target["out"] - target["in"])
            if operation.get("ripple", True):
                for c in clips:
                    if c is not target and c["start"] >= old_end:
                        c["start"] += delta
            target["in"], target["out"] = a, b
            label = f"Trimmed source range to {a / FPS:.2f}–{b / FPS:.2f}s."
        elif kind == "delete":
            clips.remove(target)
            if operation.get("ripple", True):
                for c in clips:
                    if c["start"] >= old_end:
                        c["start"] -= target["out"] - target["in"]
            label = "Deleted the selected clip" + (" and closed its gap." if operation.get("ripple", True) else "; retained the gap.")
        elif kind == "move":
            if operation.get("direction") not in ("left", "right"):
                raise ValueError("Choose left or right.")
            clips.sort(key=lambda c: c["start"])
            index = clips.index(target)
            destination = index + (-1 if operation.get("direction") == "left" else 1)
            if not 0 <= destination < len(clips):
                raise ValueError("The clip is already at that end of the timeline.")
            clips[index], clips[destination] = clips[destination], clips[index]
            start = 0
            for c in clips:
                c["start"], start = start, start + c["out"] - c["in"]
            label = "Reordered clips and closed timeline gaps."
        else:
            raise ValueError("Unsupported edit.")
    clips.sort(key=lambda c: c["start"])
    remap(project, result)
    validate(result)
    return result, label

def parse_command(text, selected, playhead):
    normalized = re.sub(r"[.!]+$", "", text.strip().lower())
    if normalized in ("split the selected clip at the playhead", "split selected clip", "split"):
        return {"type": "split", "clip": selected, "at": frame(playhead)}
    if normalized in ("delete the selected clip", "delete selected clip", "delete"):
        return {"type": "delete", "clip": selected, "ripple": True}
    match = re.fullmatch(r"trim (?:the )?selected clip (?:from )?(\d+(?:\.\d+)?) ?(?:s|seconds)? to (\d+(?:\.\d+)?) ?(?:s|seconds)?", normalized)
    if match:
        return {"type": "trim", "clip": selected, "in": round(float(match[1])*FPS),
                "out": round(float(match[2])*FPS), "ripple": True}
    match = re.fullmatch(r"move (?:the )?selected clip (left|right)", normalized)
    if match:
        return {"type": "move", "clip": selected, "direction": match[1]}
    raise ValueError("Phase 1 commands: split the selected clip at the playhead; trim selected clip from 1 to 5 seconds; delete selected clip; move selected clip left/right.")

class ProjectStore:
    def __init__(self, data_dir):
        self.directory = Path(data_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.pending = {}
        self.filepath = None
        self.undo_stack, self.redo_stack = [], []
        self.saved_revision = -1
        self.new()
        recovery = self.directory / "recovery.json"
        candidates = [p for p in [recovery, self.directory / "recovery.tmp",
                                  *self.directory.glob("recovery-*.json")]
                      if p.is_file()]
        for candidate in sorted(candidates, key=lambda p: p.stat().st_mtime_ns, reverse=True):
            try:
                self._load(candidate, recovery_mode=True)
                break
            except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError):
                pass

    def new(self):
        self.project = {"schema": 2, "id": ident(), "revision": 0, "name": "Untitled project",
                        "fps": FPS, "sample_rate": RATE, "media": [], "clips": [],
                        "original_clips": None, "chat": [], "captions": [], "transitions": [], "caption_style": {"size":54,"position":"bottom"}}
        self.filepath = None
        self.undo_stack, self.redo_stack, self.pending = [], [], {}
        self.saved_revision = -1

    def note(self, text, role="assistant", status="done", entry_id=None):
        entry = {"id": entry_id or ident(), "role": role, "status": status,
                 "text": text, "time": time.time(), "revision": self.project["revision"]}
        self.saved_revision = -1
        self.project["chat"].append(entry)
        self.project["chat"] = self.project["chat"][-200:]
        return entry

    def _expire(self):
        self.pending.clear()
        for entry in self.project["chat"]:
            if entry["status"] == "preview":
                entry["status"] = "expired"

    def _snapshot(self):
        return {k: clone(self.project.get(k, {"size":54,"position":"bottom"} if k=="caption_style" else [])) for k in ("media", "clips", "original_clips", "captions", "transitions", "caption_style")}

    def commit(self, updated, label, entry_id=None):
        before = self._snapshot()
        self.undo_stack.append({"state": before, "label": label})
        self.undo_stack = self.undo_stack[-40:]
        self.redo_stack.clear()
        self._expire()
        for key in ("media", "clips", "original_clips", "captions", "transitions", "caption_style"):
            self.project[key] = clone(updated.get(key, {"size":54,"position":"bottom"} if key=="caption_style" else []))
        self.project["revision"] += 1
        if entry_id:
            entry = next((e for e in self.project["chat"] if e["id"] == entry_id), None)
            if entry:
                entry.update(status="applied", text=label, revision=self.project["revision"])
        else:
            self.note(label, status="applied")
        self.recover()

    def edit(self, operation, revision):
        with self.lock:
            if revision != self.project["revision"]:
                raise ValueError("The project changed. Review the current selection and try again.")
            updated, label = operate(self.project, operation)
            if operation.get("type") != "append" and self.project["original_clips"] is None:
                updated["original_clips"] = clone(self.project["clips"])
            self.commit(updated, label)

    def undo(self, redo=False):
        with self.lock:
            source, destination = (self.redo_stack, self.undo_stack) if redo else (self.undo_stack, self.redo_stack)
            if not source:
                raise ValueError("Nothing to " + ("redo." if redo else "undo."))
            item = source.pop()
            destination.append({"state": self._snapshot(), "label": item["label"]})
            self._expire()
            self.project.update(clone(item["state"]))
            self.project["revision"] += 1
            self.note(("Redid: " if redo else "Undid: ") + item["label"])
            self.recover()

    def prompt(self, text, selected, playhead):
        with self.lock:
            if not isinstance(text, str) or not text.strip() or len(text) > 500:
                raise ValueError("Enter a prompt of 1–500 characters.")
            self._expire()
            self.note(text.strip(), role="user", status="prompt")
            try:
                operation = parse_command(text, selected, playhead)
                _, label = operate(self.project, operation)
            except (ValueError, KeyError, TypeError) as exc:
                self.note(str(exc), status="error")
                self.recover()
                return None
            plan_id = ident()
            self.pending[plan_id] = {"revision": self.project["revision"], "operation": operation}
            self.note("Proposed: " + label + " No change yet.", status="preview", entry_id=plan_id)
            self.recover()
            return plan_id

    def propose(self, operation, detail=""):
        with self.lock:
            _, label = operate(self.project, operation)
            self._expire()
            plan_id = ident()
            self.pending[plan_id] = {"revision":self.project["revision"],"operation":clone(operation)}
            self.note("Proposed: "+(detail or label)+" No change yet.",status="preview",entry_id=plan_id)
            self.recover()
            return plan_id

    def apply(self, plan_id):
        with self.lock:
            plan = self.pending.get(plan_id)
            if not plan or plan["revision"] != self.project["revision"]:
                raise ValueError("This preview expired or was already applied. Send the prompt again.")
            updated, label = operate(self.project, plan["operation"])
            if self.project["original_clips"] is None:
                updated["original_clips"] = clone(self.project["clips"])
            self.commit(updated, label, plan_id)

    def discard(self):
        with self.lock:
            self._expire()
            self.recover()

    def state(self):
        with self.lock:
            p = clone(self.project)
            for m in p["media"]:
                m["missing"] = not Path(m["working"]).is_file()
            return {"project": p, "duration": duration(p), "mapping": source_mapping(p),
                    "can_undo": bool(self.undo_stack), "can_redo": bool(self.redo_stack),
                    "filepath": str(self.filepath) if self.filepath else None,
                    "dirty": self.saved_revision != p["revision"], "pending": list(self.pending)}

    def recover(self):
        payload = {"project": self.project, "undo": self.undo_stack, "redo": self.redo_stack,
                   "filepath": str(self.filepath) if self.filepath else None}
        target = self.directory / "recovery.json"
        temp = self.directory / ("recovery-" + ident() + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        try:
            os.replace(temp, target)
        except PermissionError:
            # OneDrive or a backup tool may hold the existing snapshot without
            # sharing delete access. Keep the complete new snapshot separately.
            os.replace(temp, temp.with_suffix(".json"))

    def save(self, filename):
        import shutil
        with self.lock:
            target = Path(filename).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            assets = target.parent / (target.stem + ".media")
            assets.mkdir(exist_ok=True)
            data = clone(self.project)
            for media in data["media"]:
                src = Path(media["working"])
                if not src.is_file():
                    raise ValueError("Relink missing media before saving.")
                dest = assets / (media["id"] + ".mp4")
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                media["working"] = os.path.relpath(dest, target.parent)
                media["thumbnail"] = ""
            data["name"] = target.stem.replace(".vibeflow", "")
            # History is durable; transient executable plans are deliberately excluded.
            for entry in data["chat"]:
                if entry["status"] == "preview":
                    entry["status"] = "expired"
            payload = {"project": data}
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
            os.replace(temp, target)
            self.filepath = target
            self.project["name"] = data["name"]
            self.saved_revision = self.project["revision"]
            self.recover()

    def _load(self, filename, recovery_mode=False):
        target = Path(filename).resolve()
        if target.stat().st_size > 5_000_000:
            raise ValueError("Project file is too large.")
        payload = json.loads(target.read_text("utf-8"))
        candidate = payload["project"]
        candidate.setdefault("captions", [])
        candidate.setdefault("transitions", [])
        candidate.setdefault("caption_style", {"size":54,"position":"bottom"})
        candidate["schema"] = 2
        validate(candidate)
        for media in candidate["media"]:
            if not Path(media["working"]).is_absolute():
                media["working"] = str((target.parent / media["working"]).resolve())
        self.project = candidate
        self.filepath = Path(payload["filepath"]) if recovery_mode and payload.get("filepath") else (None if recovery_mode else target)
        self.undo_stack = payload.get("undo", [])[-40:] if recovery_mode else []
        self.redo_stack = payload.get("redo", [])[-40:] if recovery_mode else []
        self._expire()
        self.saved_revision = -1 if recovery_mode else candidate["revision"]
        if recovery_mode:
            self.note("Recovered the last editing session. Pending previews were not applied.")
        self.recover()

    def open(self, filename):
        with self.lock:
            self._load(filename)
