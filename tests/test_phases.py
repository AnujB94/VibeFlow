import array
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from backend.project import ProjectStore,operate,clone,duration,validate
from backend.effects import mapped_cues,ass,srt
from backend.analysis import quiet_ranges
from backend.media import Media,test_job
from backend.provider import Provider

ROOT=Path(__file__).resolve().parents[1]
class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ProjectStore(self.temp.name);self.p=self.store.project
        working=Path(self.temp.name)/"source.mp4";working.write_bytes(b"fixture")
        self.p["media"]=[{"id":"m","name":"source","frames":300,"working":str(working)}]
        self.p["clips"]=[{"id":"a","source":"m","in":25,"out":75,"start":0},
                         {"id":"b","source":"m","in":150,"out":200,"start":50}]
    def edit(self,op):self.store.edit(op,self.p["revision"])
    def test_transition_handles_odd_length_undo(self):
        self.edit({"type":"transition","left":"a","right":"b","kind":"dissolve","frames":13})
        self.assertEqual(duration(self.p),100)
        self.assertEqual(self.p["transitions"][0]["frames"],13)
        self.store.undo();self.assertEqual(self.p["transitions"],[])
        self.store.undo(True);self.assertEqual(len(self.p["transitions"]),1)
        bad=clone(self.p);bad["clips"][1]["in"]=0
        with self.assertRaises(ValueError):validate(bad)
        bad=clone(self.p);bad["transitions"].append(clone(bad["transitions"][0]))
        with self.assertRaises(ValueError):validate(bad)
    def test_caption_cut_remap_save_and_reopen(self):
        cue={"id":"c","clip":"a","in":40,"out":70,"text":"Yeh mera demo hai","raw_text":"raw","bold":["demo"],"words":[]}
        self.edit({"type":"captions","clips":["a"],"cues":[cue]})
        self.edit({"type":"cut_ranges","ranges":[[20,30],[60,70]]})
        self.assertEqual(duration(self.p),80)
        self.assertEqual([(c["start"],c["end"]) for c in mapped_cues(self.p)],[(15,20),(20,35)])
        self.assertTrue(all(c["needs_review"] for c in self.p["captions"]))
        self.assertIn(r"{\b1}demo{\b0}",ass(self.p))
        self.assertIn("00:00:00,600",srt(self.p))
        output=Path(self.temp.name)/"Edited.vibeflow"
        self.store.save(output);copy=ProjectStore(Path(self.temp.name)/"new");copy.open(output)
        self.assertEqual(copy.project["captions"],self.p["captions"])
        self.store.undo();self.assertEqual(self.p["captions"][0]["text"],cue["text"])
    def test_silence_strict_threshold_and_padding(self):
        rate=1000
        for count in (990,1000):
            samples=array.array("h",[10000]*100+[0]*count+[10000]*100)
            self.assertEqual(quiet_ranges(samples,rate,1,.12),[])
        samples=array.array("h",[10000]*100+[0]*1100+[10000]*100)
        self.assertEqual(quiet_ranges(samples,rate,1,.12),[[6,27]])
        self.assertEqual(quiet_ranges(samples,rate,1,0),[[3,30]])
    def test_proposal_atomic_and_secret_not_persisted(self):
        before=clone(self.p)
        with self.assertRaises(ValueError):
            self.store.propose({"type":"cut_ranges","ranges":[[0,200]]})
        self.assertEqual(before,self.p)
        plan=self.store.propose({"type":"cut_ranges","ranges":[[20,30]]})
        self.assertEqual(duration(self.p),100)
        self.store.apply(plan);self.assertEqual(duration(self.p),90)
        with self.assertRaises(ValueError):self.store.apply(plan)
        provider=Provider();provider.configure("test-secret","gpt-4o-mini")
        captured={}
        def request(route,data,content_type="application/json"):
            captured.update(json.loads(data))
            return {"output":[{"content":[{"type":"output_text","text":'{"words":["Yeh","demo"]}'}]}]}
        provider.request=request
        self.assertEqual(provider.romanize(["यह","demo"]),["Yeh","demo"])
        self.assertFalse(captured["store"]);self.assertNotIn("test-secret",json.dumps(captured))
    def test_romanization_rejects_english_change(self):
        provider=Provider()
        provider.structured=lambda *args:{"words":["this"]}
        with self.assertRaises(ValueError):provider.romanize(["demo"])
    def test_caption_invalid_text_atomic(self):
        with self.assertRaises(ValueError):
            self.edit({"type":"captions","clips":["a"],"cues":[{"id":"c","clip":"a","in":25,"out":50,"text":"हिंदी","bold":[]}]})
        self.assertEqual(self.p["captions"],[])

class RenderEffects(unittest.TestCase):
    def test_real_transition_caption_duration_and_audio(self):
        fixture=json.loads((ROOT/"verification"/"Acceptance.vibeflow").read_text("utf8"))["project"]
        source=fixture["media"][0];source["working"]=str((ROOT/"verification"/source["working"]).resolve())
        p={"schema":2,"fps":25,"media":[source],"clips":[
            {"id":"a","source":source["id"],"in":25,"out":75,"start":0},
            {"id":"b","source":source["id"],"in":150,"out":200,"start":50}],
            "transitions":[],"captions":[],"caption_style":{"size":60,"position":"bottom"}}
        dest=ROOT/"verification"/"phase4";dest.mkdir(exist_ok=True)
        media=Media(ROOT/"runtime"/"media",dest/"logs")
        media.render(p,dest/"hard-cut.mp4",test_job(),True)
        for kind in ("dissolve","black"):
            q=clone(p);q["transitions"]=[{"id":"t","left":"a","right":"b","kind":kind,"frames":13}]
            q["captions"]=[{"id":"c","clip":"b","in":165,"out":195,"text":"Yeh mera demo hai","raw_text":"Yeh mera demo hai","bold":["demo"],"words":[]}]
            validate(q);media.render(q,dest/(kind+".mp4"),test_job(),True)
            output=media.probe(dest/(kind+".mp4"))
            self.assertEqual(int(next(s for s in output["streams"] if s["codec_type"]=="video")["nb_frames"]),100)
        def pcm(name):
            return subprocess.run([str(media.ffmpeg),"-v","error","-i",str(dest/name),"-vn","-f","s16le","-"],capture_output=True,check=True).stdout
        self.assertEqual(pcm("hard-cut.mp4"),pcm("dissolve.mp4"))
        self.assertEqual(pcm("hard-cut.mp4"),pcm("black.mp4"))
        def rgb(name,frame):
            args=[str(media.ffmpeg),"-v","error","-i",str(dest/name),"-vf",f"select=eq(n\\,{frame}),scale=96:54","-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","-"]
            return subprocess.run(args,capture_output=True,check=True).stdout
        # Black transition is centred on the cut, with an actual black middle frame.
        center=rgb("black.mp4",50)
        self.assertLess(sum(center)/len(center),15)
        # Before the transition window the picture is unchanged apart from compression.
        a,b=rgb("hard-cut.mp4",10),rgb("dissolve.mp4",10)
        self.assertLess(sum(abs(x-y) for x,y in zip(a,b))/len(a),3)
        report={"frames":100,"seconds":4,"odd_transition_frames":13,"audio_pcm_identical":True,
                "black_center_verified":True,"caption_ass_burnin":True,"raw_speech_accuracy_tested":False,
                "live_openai_tested":False}
        (dest/"report.json").write_text(json.dumps(report,indent=2),"utf8")
if __name__=="__main__":unittest.main()
