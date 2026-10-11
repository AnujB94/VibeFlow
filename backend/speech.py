"""Caption worker orchestration; cloud audio upload is explicitly selected in the UI."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from backend.project import ident,FPS
from backend.media import Cancelled,FLAGS

def local_available(resources):
    folder=Path(resources).parent/"speech"
    return (folder/"python"/"Scripts"/"python.exe").is_file() and (folder/"model"/"model.bin").is_file()

def generate(media,provider,p,job,folder,mode):
    if mode not in ("local","openai"):raise ValueError("Select a transcription provider.")
    if mode=="local" and not local_available(media.resources):
        raise ValueError("Local speech is not installed. Run setup-speech.cmd beside Vibeflow.exe, or explicitly choose OpenAI audio upload.")
    assets={m["id"]:m for m in p["media"]};cues=[]
    for i,c in enumerate(p["clips"]):
        tmp=folder/(job["id"]+f"-speech-{i}.wav");resultfile=tmp.with_suffix(".json")
        try:
            media.execute(["-ss",c["in"]/FPS,"-t",(c["out"]-c["in"])/FPS,"-i",assets[c["source"]]["working"],
                           "-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",tmp],job,(c["out"]-c["in"])/FPS)
            if mode=="openai":
                result=provider.transcribe(tmp)
            else:
                speech=media.resources.parent/"speech"
                log=folder/(job["id"]+"-speech.log")
                with log.open("w",encoding="utf8") as err:
                    process=subprocess.Popen([str(speech/"python"/"Scripts"/"python.exe"),str(speech/"worker.py"),
                                              str(tmp),str(resultfile),str(speech/"model")],
                                             stdout=err,stderr=err,creationflags=FLAGS)
                    job["process"]=process
                    while process.poll() is None:
                        if job["cancel"].is_set():process.terminate()
                        time.sleep(.1)
                    job["process"]=None
                    if job["cancel"].is_set():raise Cancelled("Transcription cancelled.")
                    if process.returncode:raise ValueError("Local speech failed. See "+str(log))
                result=json.loads(resultfile.read_text("utf8"))
            if job["cancel"].is_set():raise Cancelled("Transcription cancelled.")
            words=result.get("words",[])
            raw=[w.get("word","").strip() for w in words]
            if not words:continue
            # Even local recognition uses the selected OpenAI text model for readable Hinglish.
            roman=provider.romanize(raw)
            timed=[]
            for w,text,original in zip(words,roman,raw):
                a=max(c["in"],c["in"]+math.floor(float(w["start"])*FPS))
                b=min(c["out"],c["in"]+math.ceil(float(w["end"])*FPS))
                if a<b:timed.append({"in":a,"out":b,"text":text,"raw_text":original})
            groups=[];group=[]
            for word in timed:
                if group and (len(group)>=7 or word["out"]-group[0]["in"]>75 or word["in"]-group[-1]["out"]>12):
                    groups.append(group);group=[]
                group.append(word)
            if group:groups.append(group)
            for group in groups:
                cues.append({"id":ident(),"clip":c["id"],"in":group[0]["in"],"out":group[-1]["out"],
                             "text":" ".join(w["text"] for w in group),"raw_text":" ".join(w["raw_text"] for w in group),
                             "words":group,"bold":[],"needs_review":True})
        finally:
            tmp.unlink(missing_ok=True);resultfile.unlink(missing_ok=True)
    if job["cancel"].is_set():raise Cancelled("Transcription cancelled.")
    keywords=provider.keywords(cues)
    for cue in cues:cue["bold"]=keywords.get(cue["id"],[])
    return cues
