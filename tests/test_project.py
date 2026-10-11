import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import os
from backend.project import ProjectStore, clone, duration, map_source_range

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProjectStore(self.temp.name)
        working = Path(self.temp.name) / "source.mp4"
        working.write_bytes(b"fixture")
        self.store.project["media"] = [{"id": "m", "name": "source", "frames": 300,
                                       "working": str(working), "thumbnail": ""}]
        self.edit(type="append", source="m")

    def edit(self, **op):
        self.store.edit(op, self.store.project["revision"])

    def test_retain_ranges_mapping_undo_save(self):
        first = self.store.project["clips"][0]["id"]
        self.edit(type="split", clip=first, at=100)
        second = self.store.project["clips"][1]["id"]
        self.edit(type="split", clip=second, at=200)
        third = self.store.project["clips"][2]["id"]
        for clip, start, end in [(third,200,250),(second,100,150),(first,0,50)]:
            self.edit(type="trim", clip=clip, **{"in":start,"out":end})
        self.assertEqual(duration(self.store.project),150)
        self.assertEqual([c["start"] for c in self.store.project["clips"]],[0,50,100])
        mapped = map_source_range(self.store.project,"m",40,210)
        self.assertEqual([(x["start"],x["end"]) for x in mapped],[(40,50),(50,100),(100,110)])
        edited = clone(self.store.project["clips"])
        self.store.undo()
        self.assertEqual(duration(self.store.project),200)
        self.store.undo(redo=True)
        self.assertEqual(self.store.project["clips"],edited)
        filename=Path(self.temp.name)/"Demo.vibeflow"
        self.store.save(filename)
        self.store.new()
        self.store.open(filename)
        self.assertEqual(self.store.project["clips"],edited)
        self.assertTrue(self.store.project["chat"])
        self.assertFalse(self.store.state()["project"]["media"][0]["missing"])

    def test_stale_and_double_apply(self):
        clip=self.store.project["clips"][0]["id"]
        plan=self.store.prompt("split the selected clip at the playhead",clip,50)
        self.store.apply(plan)
        with self.assertRaises(ValueError): self.store.apply(plan)
        plan=self.store.prompt("delete selected clip",clip,0)
        self.edit(type="split",clip=clip,at=25)
        with self.assertRaises(ValueError): self.store.apply(plan)
        with self.assertRaises(ValueError): self.store.edit({"type":"delete","clip":clip},0)

    def test_invalid_edit_atomic(self):
        before=clone(self.store.project)
        with self.assertRaises(ValueError):
            self.edit(type="trim",clip=before["clips"][0]["id"],**{"in":-1,"out":10})
        self.assertEqual(before,self.store.project)

    def test_gap_and_reorder(self):
        a=self.store.project["clips"][0]["id"]
        self.edit(type="split",clip=a,at=50)
        b=self.store.project["clips"][1]["id"]
        self.edit(type="delete",clip=a,ripple=False)
        self.assertEqual(self.store.project["clips"][0]["start"],50)
        self.store.undo()
        self.edit(type="move",clip=b,direction="left")
        self.assertEqual(self.store.project["clips"][0]["id"],b)
        self.assertEqual(duration(self.store.project),300)

    def test_recovery_survives_locked_previous_snapshot(self):
        clip = self.store.project["clips"][0]["id"]
        real_replace = os.replace
        def locked_target(source, target):
            if Path(target).name == "recovery.json":
                raise PermissionError("Previous snapshot is held by a sync tool")
            return real_replace(source, target)
        with patch("backend.project.os.replace", side_effect=locked_target):
            self.store.prompt("split", clip, 50)
            self.assertTrue(list(Path(self.temp.name).glob("recovery-*.json")))
            restored = ProjectStore(self.temp.name)
        self.assertEqual(len(restored.project["clips"]), 1)
        self.assertFalse(restored.pending)
        self.assertTrue(any(e["role"] == "user" and e["text"] == "split" for e in restored.project["chat"]))

    def test_recovery_does_not_apply_preview(self):
        clip=self.store.project["clips"][0]["id"]
        self.store.prompt("split",clip,50)
        recovered=ProjectStore(self.temp.name)
        self.assertEqual(len(recovered.project["clips"]),1)
        self.assertFalse(recovered.pending)
        self.assertTrue(recovered.undo_stack)

if __name__=="__main__": unittest.main()
