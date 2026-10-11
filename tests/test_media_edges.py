"""Small real-media edge cases. Run after npm run setup."""
import array
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from backend.media import Media, test_job, FLAGS

ROOT=Path(__file__).resolve().parent.parent
@unittest.skipUnless((ROOT/"runtime/media/ffmpeg.exe").is_file(),"Stage the bundled runtime first.")
class MediaEdges(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/".cache")
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.media=Media(ROOT/"runtime/media",self.directory/"logs")

    def test_non_25fps_and_no_audio(self):
        source=self.directory/"silent-30fps.mp4"
        self.media.execute(["-f","lavfi","-i","color=c=red:s=320x180:r=30000/1001:d=1.2",
          "-an","-c:v","libx264","-threads","2",source],test_job(),1.2)
        output=self.directory/"working.mp4"
        result=self.media.normalize(source,output,test_job())
        self.assertFalse(result["had_audio"])
        info=self.media.validate_output(output,result["frames"],1920,1080)
        video=next(s for s in info["streams"] if s["codec_type"]=="video")
        self.assertEqual(video["avg_frame_rate"],"25/1")

    def test_internal_gap_is_black_and_silent(self):
        fixture=ROOT/"verification/Acceptance.vibeflow"
        if not fixture.exists():self.skipTest("Run scripts/verify_media.py to create the reference fixture.")
        project=json.loads(fixture.read_text("utf-8"))["project"]
        source=project["media"][0]
        source["working"]=str((fixture.parent/source["working"]).resolve())
        project["clips"]=[{"id":"a","source":source["id"],"in":0,"out":25,"start":0},
                          {"id":"b","source":source["id"],"in":100,"out":125,"start":50}]
        output=self.directory/"gap.mp4"
        self.media.render(project,output,test_job(),True)
        result=subprocess.run([str(self.media.ffmpeg),"-v","error","-ss","1.4","-i",str(output),
          "-frames:v","1","-vf","scale=16:16","-pix_fmt","rgb24","-f","rawvideo","pipe:1"],
          capture_output=True,check=True,creationflags=FLAGS)
        self.assertEqual(len(result.stdout),16*16*3)
        self.assertLess(max(result.stdout),3)
        result=subprocess.run([str(self.media.ffmpeg),"-v","error","-ss","1.2","-i",str(output),
          "-t","0.5","-vn","-ac","1","-f","f32le","pipe:1"],
          capture_output=True,check=True,creationflags=FLAGS)
        samples=array.array("f");samples.frombytes(result.stdout)
        self.assertLess(max(abs(x) for x in samples),.005)

if __name__=="__main__":unittest.main()
