import json
import os
from pathlib import Path
import threading
import time
import traceback
from backend.project import ProjectStore, clone, ident, validate
from backend.media import Media, Cancelled

class Service:
    def __init__(self, data, resources, emit=lambda event: None):
        from backend.provider import Provider
        self.provider = Provider()
        self.data = Path(data)
        self.store = ProjectStore(self.data)
        self.media = Media(resources, self.data / "logs")
        self.emit = emit
        self.job = None
        self.preview = None
        self.worker = None
        self.job_lock = threading.RLock()
        (self.data / "media").mkdir(exist_ok=True)
        (self.data / "renders").mkdir(exist_ok=True)

    def job_state(self):
        if not self.job:
            return None
        return {k: self.job.get(k) for k in ("id", "kind", "revision", "status", "progress", "message", "output", "seconds")}

    def state(self):
        from backend.speech import local_available
        return {"provider":{"configured":bool(self.provider.key),"model":self.provider.model,"local_speech":local_available(self.media.resources)}, **self.store.state(), "job": self.job_state(), "preview": self.preview,
                "diagnostics": str(self.data / "logs")}

    def notify(self):
        self.emit({"event": "state", "data": self.state()})

    def cancel(self):
        with self.job_lock:
            if self.job and self.job["status"] == "running":
                self.job["cancel"].set()
                process = self.job.get("process")
                if process and process.poll() is None:
                    try:
                        process.terminate()
                    except OSError:
                        pass

    def start(self, kind, task):
        with self.job_lock:
            if self.job and self.job["status"] == "running":
                raise ValueError("Wait for the current job, or cancel it first.")
            job = {"id": ident(), "kind": kind, "revision": self.store.project["revision"],
                   "project_id": self.store.project["id"], "status": "running", "progress": 0,
                   "message": kind.capitalize() + " in progress", "cancel": threading.Event(), "process": None}
            self.job = job
            last_emit = [0]
            def progress():
                if time.monotonic() - last_emit[0] > .25:
                    last_emit[0] = time.monotonic()
                    self.emit({"event": "job", "data": self.job_state()})
            job["notify"] = progress
            def work():
                started = time.monotonic()
                try:
                    task(job)
                    if job["status"] == "running":
                        job.update(status="done", progress=1)
                except Cancelled as exc:
                    job.update(status="cancelled", message=str(exc))
                except Exception as exc:
                    job.update(status="error", message=str(exc))
                    with (self.data / "logs" / "backend.log").open("a", encoding="utf-8") as out:
                        traceback.print_exc(file=out)
                finally:
                    job["seconds"] = round(time.monotonic() - started, 3)
                    if job["status"] in ("error", "cancelled", "stale"):
                        with self.store.lock:
                            self.store.note(job["kind"].capitalize() + ": " + job["message"], status=job["status"])
                            self.store.recover()
                    self.notify()
            self.worker = threading.Thread(target=work, daemon=True)
            self.worker.start()
        return self.state()

    def import_media(self, filename=None, relink=None, demo=False):
        project_id = self.store.project["id"]
        def task(job):
            media_id = relink or ident()
            destination = self.data / "media" / (media_id + "-" + job["id"] + ".mp4")
            temp = destination.with_suffix(".partial.mp4")
            demo_path = self.data / "media" / "frame-counter-original.mp4"
            try:
                source = filename
                if demo:
                    self.media.demo(demo_path, job)
                    source = str(demo_path)
                properties = self.media.normalize(source, temp, job)
                if job["cancel"].is_set():
                    raise Cancelled("Import cancelled.")
                with self.store.lock:
                    if self.store.project["id"] != project_id:
                        raise Cancelled("Project changed. Import discarded.")
                    updated = clone(self.store.project)
                    media = {"id": media_id, "name": Path(source).name, "original": str(source),
                             "working": str(destination), "thumbnail": "", **properties}
                    if relink:
                        if not any(m["id"] == relink for m in updated["media"]):
                            raise ValueError("The media to relink no longer exists.")
                        updated["media"] = [media if m["id"] == relink else m for m in updated["media"]]
                    else:
                        updated["media"].append(media)
                    validate(updated)
                    os.replace(temp, destination)
                    self.store.commit(updated, ("Relinked " if relink else "Imported ") + media["name"])
                    job["message"] = "Media ready. Add it to the timeline."
            finally:
                temp.unlink(missing_ok=True)
        return self.start("import", task)

    def render(self, preview, filename=None):
        with self.store.lock:
            snapshot = clone(self.store.project)
        if not snapshot["clips"]:
            raise ValueError("Add a clip to the timeline first.")
        def task(job):
            destination = self.data / "renders" / (job["id"] + ".mp4") if preview else Path(filename).resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp = destination.with_name(destination.stem + "." + job["id"] + ".partial.mp4")
            try:
                self.media.render(snapshot, temp, job, preview)
                with self.store.lock:
                    if job["cancel"].is_set():
                        raise Cancelled("Render cancelled. Partial output discarded.")
                    current = self.store.project
                    if (snapshot["id"], snapshot["revision"]) != (current["id"], current["revision"]):
                        job.update(status="stale", message="Project changed during rendering. Refresh to render the latest edit.")
                        return
                    os.replace(temp, destination)
                    job.update(output=str(destination), message="Preview ready." if preview else "Exported " + destination.name)
                    if preview:
                        self.preview = {"path": str(destination), "revision": snapshot["revision"], "project_id": snapshot["id"]}
                    else:
                        self.store.note("Exported " + destination.name)
                        self.store.recover()
            finally:
                temp.unlink(missing_ok=True)
        return self.start("preview" if preview else "export", task)

    def check_current(self, snapshot, job):
        if job["cancel"].is_set():
            raise Cancelled("Cancelled. Result discarded.")
        if (snapshot["id"],snapshot["revision"]) != (self.store.project["id"],self.store.project["revision"]):
            raise Cancelled("Project changed. Result discarded; try again.")

    def analyze(self, params):
        from backend.analysis import find_pauses
        with self.store.lock: snapshot=clone(self.store.project)
        threshold=float(params.get("threshold",1));padding=float(params.get("padding",.12));db=float(params.get("db",-38))
        def task(job):
            ranges=find_pauses(self.media,snapshot,job,self.data/"renders",threshold,padding,db)
            with self.store.lock:
                self.check_current(snapshot,job)
                if ranges:self.store.propose({"type":"cut_ranges","ranges":ranges})
                else:self.store.note("No pauses longer than the threshold were found.");self.store.recover()
            job["message"]="Pause analysis ready. Review the proposed ranges in chat."
        return self.start("pause analysis",task)

    def prompt(self, params):
        from backend.project import parse_command
        text=params["text"]
        if not isinstance(text,str) or not 1<=len(text.strip())<=500:raise ValueError("Enter 1–500 characters.")
        # Familiar explicit commands remain usable without a key or network.
        try:
            operation=parse_command(text,params.get("selected"),params.get("playhead",0))
        except ValueError:
            operation=None
        if operation:
            self.store.prompt(text,params.get("selected"),params.get("playhead",0))
            return self.state()
        with self.store.lock:
            self.store.discard()
            self.store.note(text,role="user",status="prompt")
            self.store.recover()
            snapshot=clone(self.store.project)
        def task(job):
            op,message=self.provider.plan(text,snapshot,params.get("selected"),params.get("playhead",0))
            if op and op["type"]=="generate_captions":
                from backend.speech import generate
                cues=generate(self.media,self.provider,snapshot,job,self.data/"renders","local")
                op={"type":"captions","clips":[c["id"] for c in snapshot["clips"]],"cues":cues} if cues else None
                message="No speech detected; existing captions were kept." if not cues else ""
            if op and op["type"]=="silence":
                from backend.analysis import find_pauses
                ranges=find_pauses(self.media,snapshot,job,self.data/"renders",float(op["threshold"]))
                op={"type":"cut_ranges","ranges":ranges} if ranges else None
                message="No qualifying pauses found." if not ranges else ""
            with self.store.lock:
                self.check_current(snapshot,job)
                if op:
                    details=""
                    if op.get("clip"):
                        c=next((c for c in snapshot["clips"] if c["id"]==op["clip"]),None)
                        if c:
                            details=f"{op['type'].capitalize()} clip {snapshot['clips'].index(c)+1}, timeline {c['start']/25:.2f}–{(c['start']+c['out']-c['in'])/25:.2f}s. "
                    from backend.project import operate
                    _,label=operate(snapshot,op)
                    self.store.propose(op,details+label)
                else:self.store.note(message or "Please clarify the requested edit.");self.store.recover()
            job["message"]="Review the response in chat."
        return self.start("assistant",task)

    def captions(self, params):
        from backend.speech import generate
        if not self.provider.key:raise ValueError("Add an OpenAI key in Settings for Roman-Hinglish text cleanup.")
        with self.store.lock:snapshot=clone(self.store.project)
        if not snapshot["clips"]:raise ValueError("Add video to the timeline first.")
        mode=params.get("mode","local")
        def task(job):
            cues=generate(self.media,self.provider,snapshot,job,self.data/"renders",mode)
            with self.store.lock:
                self.check_current(snapshot,job)
                if cues:self.store.propose({"type":"captions","clips":[c["id"] for c in snapshot["clips"]],"cues":cues},
                                          f"Replace captions on {len(snapshot['clips'])} timeline clips with {len(cues)} Roman-Hinglish cues. First cues: "+" | ".join(c["text"] for c in cues[:5]))
                else:self.store.note("No speech detected. Existing captions were kept.");self.store.recover()
            job["message"]="Captions ready for review in chat."
        return self.start("captions",task)

    def call(self, method, params):
        if method == "state":
            return self.state()
        if method in ("new", "open"):
            if self.job and self.job["status"] == "running":
                raise ValueError("Cancel or finish the current job before changing projects.")
            if method == "new":
                with self.store.lock:
                    self.store.new()
                    self.store.recover()
            else:
                self.store.open(params["filename"])
            self.preview = None
        elif method == "save":
            self.store.save(params["filename"])
        elif method == "edit":
            self.store.edit(params["operation"], params["revision"])
        elif method in ("undo", "redo"):
            self.store.undo(method == "redo")
        elif method == "prompt":
            return self.prompt(params)
        elif method == "settings":
            self.provider.configure(params.get("key",""),params.get("model","gpt-4o-mini"))
        elif method == "analyze":
            return self.analyze(params)
        elif method == "captions":
            return self.captions(params)
        elif method == "propose":
            self.store.propose(params["operation"])
        elif method == "srt":
            from backend.effects import srt
            Path(params["filename"]).write_text(srt(self.store.project),"utf8")
        elif method == "apply":
            self.store.apply(params["plan_id"])
        elif method == "discard":
            self.store.discard()
        elif method == "import":
            return self.import_media(params["filename"], params.get("relink"))
        elif method == "demo":
            return self.import_media(demo=True)
        elif method in ("preview", "export"):
            return self.render(method == "preview", params.get("filename"))
        elif method == "cancel":
            self.cancel()
        else:
            raise ValueError("Unknown backend method.")
        return self.state()

    def close(self):
        self.cancel()
        if self.worker:
            self.worker.join(timeout=5)
