"""Real FFmpeg acceptance fixtures. Writes reviewable media and JSON evidence."""
import array
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.media import Media,test_job,FLAGS
from backend.project import clone,ident,duration
from backend.service import Service

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"verification"
OUT.mkdir(exist_ok=True)
media=Media(ROOT/"runtime/media",OUT/"logs")
def wait(service):
    service.worker.join(180)
    assert not service.worker.is_alive(),"Job timeout"
    return service.job
def good(job):
    assert job["status"]=="done",job
def edit(service,**operation):
    service.store.edit(operation,service.store.project["revision"])
report={}
started=time.monotonic()
service=Service(OUT/"session",ROOT/"runtime/media")
service.store.new()
service.import_media(demo=True);good(wait(service))
asset=service.store.project["media"][0]
report["import_seconds"]=service.job["seconds"]
edit(service,type="append",source=asset["id"])
a=service.store.project["clips"][0]["id"]
edit(service,type="split",clip=a,at=100)
b=service.store.project["clips"][1]["id"]
edit(service,type="split",clip=b,at=200)
c=service.store.project["clips"][2]["id"]
for clip,start,end in [(c,200,250),(b,100,150),(a,0,50)]:
    edit(service,type="trim",clip=clip,**{"in":start,"out":end})
snapshot=clone(service.store.project)
assert duration(snapshot)==150
target=OUT/"six-second-edit.mp4"
service.render(False,target);good(wait(service))
report["six_second_export_seconds"]=service.job["seconds"]
media.validate_output(target,150,1920,1080)
# Decode source and destination frames to RGB and compare cut boundaries.
def pixels(file,frame):
    result=subprocess.run([str(media.ffmpeg),"-v","error","-ss",str(frame/25),"-i",str(file),
      "-frames:v","1","-vf","scale=160:90","-f","rawvideo","-pix_fmt","rgb24","pipe:1"],
      capture_output=True,creationflags=FLAGS,check=True)
    return result.stdout
errors=[]
for output,source in [(0,0),(24,24),(49,49),(50,100),(99,149),(100,200),(149,249)]:
    actual,expected=pixels(target,output),pixels(asset["working"],source)
    assert len(actual)==len(expected)==160*90*3
    error=sum(abs(a-b) for a,b in zip(actual,expected))/len(actual)
    assert error<4,(output,source,error)
    errors.append({"output_frame":output,"source_frame":source,"mean_rgb_error":round(error,3)})
report["boundary_checks"]=errors
pcm=subprocess.run([str(media.ffmpeg),"-v","error","-i",str(target),"-vn","-ac","1","-ar","48000",
 "-f","f32le","pipe:1"],capture_output=True,creationflags=FLAGS,check=True).stdout
samples=array.array("f");samples.frombytes(pcm)
if sys.byteorder!="little":samples.byteswap()
onsets=[]
for second in range(6):
    start=second*48000
    active=next((i for i in range(start,min(start+4800,len(samples))) if abs(samples[i])>.1),None)
    assert active is not None
    offset=(active-start)/48000
    assert offset<.04,(second,offset)
    assert max(abs(x) for x in samples[start+12000:start+24000])<.03
    onsets.append(round(second+offset,5))
report["audio_pulse_onsets_seconds"]=onsets
service.store.undo();service.store.undo(redo=True)
assert service.store.project["clips"]==snapshot["clips"]
service.store.save(OUT/"Acceptance.vibeflow")
service.store.open(OUT/"Acceptance.vibeflow")
assert service.store.project["clips"]==snapshot["clips"] and service.store.project["chat"]
report["undo_save_reopen_history"]="passed"
# Start a real render then edit immediately; it must not publish.
service.render(True)
edit(service,type="split",clip=a,at=25)
job=wait(service)
assert job["status"]=="stale" and service.preview is None,job
report["edit_during_render"]="stale output discarded"
service.render(True);service.cancel();job=wait(service)
assert job["status"]=="cancelled",job
service.render(True);good(wait(service))
assert service.preview["revision"]==service.store.project["revision"]
report["cancel_then_rerender"]="passed"
# Deliberate missing-media and relink workflow.
working=Path(service.store.project["media"][0]["working"])
backup=working.with_suffix(".held.mp4")
working.rename(backup)
try:
    assert service.state()["project"]["media"][0]["missing"]
    service.import_media(str(backup),relink=asset["id"]);good(wait(service))
    assert not service.state()["project"]["media"][0]["missing"]
finally:
    backup.rename(working)
report["missing_media_relink"]="passed"
# Ten-second refresh benchmark using the normalized reference footage.
bench=clone(snapshot)
bench["clips"]=[{"id":ident(),"source":asset["id"],"in":0,"out":250,"start":0}]
for label,project,preview in [("preview_10s",bench,True)]:
    start=time.monotonic()
    media.render(project,OUT/(label+".mp4"),test_job(),preview)
    report[label+"_seconds"]=round(time.monotonic()-start,3)
# 180s at 1080p, repeating the same detailed test clip.
bench["clips"]=[{"id":ident(),"source":asset["id"],"in":0,"out":300,"start":i*300} for i in range(15)]
start=time.monotonic()
media.render(bench,OUT/"export_180s.mp4",test_job())
report["export_180s_seconds"]=round(time.monotonic()-start,3)
# Tiny compatibility probes for later phases, no feature claims.
fontdir=str(media.resources/"fonts").replace("\\","/").replace(":","\\:")
ass=OUT/"roman-hinglish.ass"
ass.write_text("""[Script Info]
ScriptType: v4.00+
PlayResX: 640
PlayResY: 360
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,20,20,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Aaj hum {\\b1}video edit{\\b0} karenge.
""","utf-8")
asspath=str(ass).replace("\\","/").replace(":","\\:")
media.execute(["-f","lavfi","-i","color=c=gray:s=640x360:r=25:d=1","-vf",
 f"subtitles=filename='{asspath}':fontsdir='{fontdir}'","-c:v","libx264","-threads","4","-pix_fmt","yuv420p",OUT/"probe-captions.mp4"],test_job(),1)
media.execute(["-f","lavfi","-i","color=c=red:s=640x360:r=25:d=1",
 "-f","lavfi","-i","color=c=blue:s=640x360:r=25:d=1","-filter_complex",
 "[0:v][1:v]xfade=transition=fade:duration=0.4:offset=0.6[v]","-map","[v]",
 "-c:v","libx264","-threads","4","-pix_fmt","yuv420p",OUT/"probe-transition.mp4"],test_job(),1.6)
media.execute(["-i",asset["working"],"-t","1","-vf","crop=608:1080:656:0,scale=1080:1920",
 "-an","-c:v","libx264","-threads","4","-preset","ultrafast","-pix_fmt","yuv420p",OUT/"probe-vertical.mp4"],test_job(),1)
for filename,frames,width,height in [("probe-captions.mp4",25,640,360),("probe-transition.mp4",40,640,360),("probe-vertical.mp4",25,1080,1920)]:
    stream=next(x for x in media.probe(OUT/filename)["streams"] if x["codec_type"]=="video")
    assert (int(stream["nb_frames"]),stream["width"],stream["height"])==(frames,width,height),stream
report["future_filter_probes"]=["Roman Hinglish with bold ASS text","cross dissolve","1080x1920 crop"]
report["machine"]={"platform":platform.platform(),"processor":platform.processor(),"logical_cpus":os.cpu_count()}
if os.name=="nt":
    import ctypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
          ("total_phys","avail_phys","total_page","avail_page","total_virtual","avail_virtual","avail_extended")]
    memory=MEMORYSTATUSEX();memory.length=ctypes.sizeof(memory);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    report["machine"]["ram_gib"]=round(memory.total_phys/1024**3,1)
report["ffmpeg"]=subprocess.check_output([str(media.ffmpeg),"-version"],creationflags=FLAGS,text=True).splitlines()[0]
report["total_seconds"]=round(time.monotonic()-started,3)
report["targets"]={"preview_under_5_seconds":report["preview_10s_seconds"]<=5,
                   "export_under_180_seconds":report["export_180s_seconds"]<=180}
(OUT/"report.json").write_text(json.dumps(report,indent=2),"utf-8")
print(json.dumps(report,indent=2))
