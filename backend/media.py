"""Shared media preparation and preview/export renderer. No third-party Python packages."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from backend.project import FPS, RATE, MAX_FRAMES, duration

FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

class Cancelled(Exception):
    pass

class Media:
    def __init__(self, resources, logs):
        self.resources = Path(resources)
        self.ffmpeg = self.resources / "ffmpeg.exe"
        self.ffprobe = self.resources / "ffprobe.exe"
        self.logs = Path(logs)
        self.logs.mkdir(parents=True, exist_ok=True)
        for binary in (self.ffmpeg, self.ffprobe):
            if not binary.is_file():
                raise ValueError(f"Missing bundled runtime: {binary}")

    def probe(self, filename, count=False):
        args = [str(self.ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json"]
        if count:
            args.append("-count_frames")
        args.append(str(filename))
        result = subprocess.run(args, capture_output=True, creationflags=FLAGS, timeout=90)
        if result.returncode:
            raise ValueError("Could not read this media file. " + result.stderr.decode(errors="replace")[-800:])
        return json.loads(result.stdout)

    def execute(self, args, job, seconds):
        log = self.logs / (job["id"] + ".log")
        command = [str(self.ffmpeg), "-hide_banner", "-nostdin", "-y", "-threads", "4",
                   "-filter_complex_threads", "2", "-progress", "pipe:1", "-nostats"] + list(map(str, args))
        with log.open("w", encoding="utf-8") as stderr:
            stderr.write(json.dumps({"job": job["id"], "revision": job.get("revision"), "command": command}) + "\n")
            stderr.flush()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr,
                                       text=True, encoding="utf-8", errors="replace", creationflags=FLAGS)
            job["process"] = process
            if job["cancel"].is_set():
                process.terminate()
            for line in process.stdout:
                if job["cancel"].is_set() and process.poll() is None:
                    process.terminate()
                if line.startswith("out_time_us="):
                    try:
                        job["progress"] = min(.99, max(0, int(line.split("=")[1]) / 1_000_000 / max(seconds, .01)))
                        job["notify"]()
                    except ValueError:
                        pass
            process.stdout.close()
            code = process.wait()
            job["process"] = None
        if job["cancel"].is_set():
            raise Cancelled("Cancelled. Partial output was discarded.")
        if code:
            tail = log.read_text("utf-8")[-2200:]
            raise ValueError("FFmpeg could not complete this job. Open diagnostics for details.\n" + tail[-600:])

    def validate_output(self, filename, frames, width, height):
        info = self.probe(filename)
        video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        if not video or not audio:
            raise ValueError("Rendered file is missing linked video or audio.")
        if int(video.get("nb_frames", -1)) != frames or (video["width"], video["height"]) != (width, height):
            raise ValueError("Rendered frame count or dimensions did not match the project.")
        if abs(float(audio.get("duration", 0)) - frames/FPS) > .05:
            raise ValueError("Rendered audio duration did not match the project.")
        return info

    def normalize(self, source, destination, job):
        info = self.probe(source)
        video = next((s for s in info["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")), None)
        if not video:
            raise ValueError("Choose a video file.")
        rotation = video.get("tags", {}).get("rotate", 0)
        rotation = next((s.get("rotation", rotation) for s in video.get("side_data_list", []) if "rotation" in s), rotation)
        if float(rotation) % 360:
            raise ValueError("Rotated footage is outside this demo. Export it as a landscape SDR clip first.")
        if video.get("color_transfer") in ("smpte2084", "arib-std-b67"):
            raise ValueError("HDR footage is outside this demo. Convert it to SDR before import.")
        if video["width"] > 1920 or video["height"] > 1080 or video["width"] < video["height"]:
            raise ValueError("Phase 1 accepts landscape SDR video up to 1920 × 1080.")
        seconds = float(video.get("duration") or info["format"].get("duration") or 0)
        frames = round(seconds * FPS)
        if not 1 <= frames <= MAX_FRAMES:
            raise ValueError("Choose a video between one frame and three minutes.")
        seconds = frames/FPS
        has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
        args = ["-i", source]
        if not has_audio:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        args += ["-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
                 "-vf", "setpts=PTS-STARTPTS,fps=25,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=1",
                 "-af", "aresample=48000:async=1:first_pts=0,apad",
                 "-t", f"{seconds:.8f}", "-r", "25",
                 "-c:v", "libx264", "-threads", "4", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-movflags", "+faststart", destination]
        self.execute(args, job, seconds)
        self.validate_output(destination, frames, 1920, 1080)
        return {"frames": frames, "width": 1920, "height": 1080, "had_audio": has_audio}

    def render(self, project, destination, job, preview=False):
        frames = duration(project)
        if not frames:
            raise ValueError("Add a clip to the timeline first.")
        size = (960, 540) if preview else (1920, 1080)
        assets = {m["id"]: m for m in project["media"]}
        args, filters, segments = [], [], []
        cursor, input_index = 0, 0
        for clip in sorted(project["clips"], key=lambda c: c["start"]):
            if clip["start"] > cursor:
                n = clip["start"] - cursor
                i = len(segments)
                filters += [f"color=c=black:s={size[0]}x{size[1]}:r=25:d={n/FPS},trim=end_frame={n},setpts=PTS-STARTPTS[v{i}]",
                            f"anullsrc=r=48000:cl=stereo,atrim=end_sample={n*1920},asetpts=PTS-STARTPTS[a{i}]"]
                segments.append(f"[v{i}][a{i}]")
            filename = assets[clip["source"]]["working"]
            if not Path(filename).is_file():
                raise ValueError("Media is missing. Relink it from the media panel.")
            n = clip["out"] - clip["in"]
            args += ["-ss", f"{clip['in']/FPS:.8f}", "-t", f"{n/FPS:.8f}", "-i", filename]
            i = len(segments)
            filters += [f"[{input_index}:v]trim=end_frame={n},setpts=PTS-STARTPTS,scale={size[0]}:{size[1]},setsar=1[v{i}]",
                        f"[{input_index}:a]atrim=end_sample={n*1920},asetpts=PTS-STARTPTS[a{i}]"]
            segments.append(f"[v{i}][a{i}]")
            input_index += 1
            cursor = clip["start"] + n
        filters.append("".join(segments) + f"concat=n={len(segments)}:v=1:a=1[v][a]")
        video_label="v"
        by_id={c["id"]:c for c in project["clips"]}
        for ti,t in enumerate(project.get("transitions",[])):
            left,right=by_id[t["left"]],by_id[t["right"]]
            n=t["frames"];before=n//2;cut=right["start"];start=cut-before
            for side,clip,source_in in (("l",left,left["out"]-before),("r",right,right["in"]-before)):
                args += ["-ss",f"{source_in/FPS:.8f}","-t",f"{n/FPS:.8f}","-i",assets[clip["source"]]["working"]]
                filters.append(f"[{input_index}:v]trim=end_frame={n},setpts=PTS-STARTPTS,scale={size[0]}:{size[1]},setsar=1[t{ti}{side}]")
                input_index+=1
            # Blend full handle windows; audio remains the unchanged hard-cut track.
            length=max(1,n-1)/FPS
            expr=f"A*(1-T/{length})+B*T/{length}" if t["kind"]=="dissolve" else f"if(lt(T,{before/FPS}),A*(1-T/{before/FPS}),B*(T-{before/FPS})/{max(1,n-1-before)/FPS})"
            if t["kind"]=="black":
                filters.append(f"[t{ti}l]fade=t=out:st=0:d={before/FPS}[tf{ti}l]")
                filters.append(f"[t{ti}r]fade=t=in:st={before/FPS}:d={max(1,n-1-before)/FPS}[tf{ti}r]")
                labels=f"[tf{ti}l][tf{ti}r]"
                expr=f"if(lt(T,{before/FPS}),A,B)"
            else: labels=f"[t{ti}l][t{ti}r]"
            filters.append(f"{labels}blend=all_expr='{expr}':shortest=1,setpts=PTS+{start/FPS}/TB[tw{ti}]")
            next_label=f"tv{ti}"
            filters.append(f"[{video_label}][tw{ti}]overlay=eof_action=pass:repeatlast=0:enable='gte(t,{start/FPS})*lt(t,{(start+n)/FPS})'[{next_label}]")
            video_label=next_label
        caption_file=None
        if project.get("captions"):
            from backend.effects import ass
            caption_file=self.logs/(job["id"]+".ass")
            caption_file.write_text(ass(project),"utf8")
            escaped=str(caption_file).replace("\\","/").replace(":","\\:").replace("'","\\'")
            fonts=str(self.resources/"fonts").replace("\\","/").replace(":","\\:").replace("'","\\'")
            filters.append(f"[{video_label}]ass=filename='{escaped}':fontsdir='{fonts}'[captioned]")
            video_label="captioned"
        args += ["-filter_complex", ";".join(filters), "-map", "["+video_label+"]", "-map", "[a]",
                 "-t", f"{frames/FPS:.8f}", "-r", "25", "-c:v", "libx264", "-threads", "4",
                 "-preset", "ultrafast" if preview else "veryfast", "-crf", "25" if preview else "20",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                 "-b:a", "192k", "-movflags", "+faststart", destination]
        self.execute(args, job, frames/FPS)
        self.validate_output(destination, frames, *size)

    def demo(self, destination, job):
        # Frame numbers plus a 60 ms tone on each source second.
        font = str(self.resources / "fonts" / "DejaVuSans.ttf").replace("\\", "/").replace(":", "\\:")
        args = ["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=12",
                "-f", "lavfi", "-i", "aevalsrc=if(lt(mod(t\\,1)\\,0.06)\\,0.6*sin(2*PI*880*t)\\,0):s=48000:d=12",
                "-vf", f"drawtext=fontfile='{font}':text='SOURCE FRAME %{{n}}':fontsize=56:fontcolor=white:box=1:boxcolor=black:x=40:y=40",
                "-c:v", "libx264", "-threads", "4", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-t", "12", destination]
        self.execute(args, job, 12)

def test_job():
    return {"id": "test-" + str(time.time_ns()), "revision": 0, "cancel": threading.Event(),
            "process": None, "progress": 0, "notify": lambda: None}
