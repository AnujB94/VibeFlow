"""Cumulative demo fixture and service-level Phase 3 check."""
import json,time
from pathlib import Path
from backend.service import Service
from backend.project import clone,duration
from backend.media import test_job
root=Path(__file__).resolve().parents[1]
folder=root/"verification"/"phase4"
service=Service(folder/"service-session",root/"runtime"/"media")
seed=json.loads((root/"verification"/"Acceptance.vibeflow").read_text("utf8"))["project"]
asset=seed["media"][0]
asset["working"]=str((root/"verification"/asset["working"]).resolve())
service.store.new()
p=service.store.project;p["media"]=[asset]
p["clips"]=[{"id":"demo-a","source":asset["id"],"in":25,"out":75,"start":0},
            {"id":"demo-b","source":asset["id"],"in":100,"out":150,"start":50},
            {"id":"demo-c","source":asset["id"],"in":175,"out":225,"start":100}]
for left,right,kind,n in [("demo-a","demo-b","dissolve",13),("demo-b","demo-c","black",15)]:
    service.store.edit({"type":"transition","left":left,"right":right,"kind":kind,"frames":n},p["revision"])
cues=[{"id":"demo-caption","clip":"demo-b","in":112,"out":145,"text":"Yeh mera demo hai",
       "raw_text":"Yeh mera demo hai","bold":["demo"],"words":[],"needs_review":False}]
service.store.edit({"type":"captions","clips":["demo-b"],"cues":cues},p["revision"])
service.store.save(folder/"Phase4Demo.vibeflow")
service.media.render(clone(p),folder/"demo-1080p.mp4",test_job(),False)
service.call("analyze",{"threshold":.5,"padding":.12,"db":-38})
service.worker.join(30)
assert service.job["status"]=="done",service.job
assert service.store.pending,"The pulse fixture must expose pauses"
plan_id=next(iter(service.store.pending));ranges=service.store.pending[plan_id]["operation"]["ranges"]
assert len(ranges)>=3,ranges
before=duration(p);service.store.apply(plan_id)
assert duration(p)==before-sum(b-a for a,b in ranges)
service.media.render(clone(p),folder/"after-pauses.mp4",test_job(),True)
after=duration(p);service.store.undo();assert duration(p)==before
service.close()
(folder/"service-report.json").write_text(json.dumps({"two_transitions_1080p":True,
    "caption_burnin":True,"pause_proposal_ranges":ranges,"frames_before":before,
    "frames_after":after,"pause_apply_render_undo":True},indent=2),"utf8")
print((folder/"service-report.json").read_text("utf8"))
