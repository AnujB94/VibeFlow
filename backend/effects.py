"""Validated timeline effects; all times are integer 25 fps frames."""
import math
import re
from backend.project import clone, ident, frame, FPS, duration

def validate_effects(p):
    clips = {c["id"]: c for c in p["clips"]}
    media = {m["id"]: m for m in p["media"]}
    windows = []
    for t in p.get("transitions", []):
        left, right = clips.get(t["left"]), clips.get(t["right"])
        n = frame(t["frames"])
        if not left or not right or t["kind"] not in ("dissolve", "black") or not 2 <= n <= 125:
            raise ValueError("Choose a dissolve or fade through black, between 2 and 125 frames.")
        before, after = n//2, n-n//2
        cut = left["start"] + left["out"]-left["in"]
        if cut != right["start"]:
            raise ValueError("Transitions require adjacent clips with no gap.")
        if left["out"] + after > media[left["source"]]["frames"] or right["in"] < before:
            raise ValueError("Not enough source handles. Trim the left clip's end and the right clip's beginning first.")
        if before > left["out"]-left["in"] or after > right["out"]-right["in"]:
            raise ValueError("The transition is longer than the adjacent clips.")
        windows.append((cut-before, cut+after))
    windows.sort()
    if any(a[1] > b[0] for a,b in zip(windows, windows[1:])):
        raise ValueError("Transition windows overlap. Shorten or remove a transition.")
    seen = set()
    for c in p.get("captions", []):
        target = clips.get(c["clip"])
        if c["id"] in seen or not target:
            raise ValueError("Invalid caption reference.")
        seen.add(c["id"])
        if not target["in"] <= frame(c["in"]) < frame(c["out"]) <= target["out"]:
            raise ValueError("Caption timing must stay inside its source clip.")
        if not isinstance(c["text"], str) or len(c["text"]) > 500 or not c["text"].strip():
            raise ValueError("Caption text must contain 1–500 characters.")
        if re.search(r"[\u0900-\u097f]", c["text"]):
            raise ValueError("Use Roman script for Hindi words in captions.")
        if not isinstance(c.get("bold", []), list) or any(not isinstance(w,str) for w in c.get("bold",[])):
            raise ValueError("Bold keywords must be a list of words.")
    style = p.get("caption_style", {})
    if not 20 <= style.get("size", 54) <= 120 or style.get("position","bottom") not in ("top","middle","bottom"):
        raise ValueError("Caption size must be 20–120; position top, middle or bottom.")

def remap(before, after):
    captions = []
    for cue in before.get("captions", []):
        for clip in after["clips"]:
            if clip.get("_parent",clip["id"]) != cue["clip"]:
                continue
            a,b = max(cue["in"],clip["in"]),min(cue["out"],clip["out"])
            if a >= b:
                continue
            partial = (a,b) != (cue["in"],cue["out"])
            words = [w for w in cue.get("words",[]) if w["out"] > a and w["in"] < b]
            text = " ".join(w["text"] for w in words) if partial and words else cue["text"]
            captions.append({**cue,"id":ident() if clip["id"]!=cue["clip"] else cue["id"],
                             "clip":clip["id"],"in":a,"out":b,"text":text,"words":words,
                             "needs_review":cue.get("needs_review",False) or partial})
    after["captions"] = captions
    transitions = []
    for t in before.get("transitions",[]):
        oldl = next(c for c in before["clips"] if c["id"]==t["left"])
        oldr = next(c for c in before["clips"] if c["id"]==t["right"])
        left = next((c for c in after["clips"] if c.get("_parent",c["id"])==t["left"] and c["out"]==oldl["out"]),None)
        right = next((c for c in after["clips"] if c.get("_parent",c["id"])==t["right"] and c["in"]==oldr["in"]),None)
        if left and right and left["start"]+left["out"]-left["in"]==right["start"]:
            transitions.append({**t,"left":left["id"],"right":right["id"]})
    after["transitions"] = transitions
    for clip in after["clips"]:
        clip.pop("_parent",None)

def special(p, op):
    kind=op.get("type")
    if kind not in ("transition","remove_transition","cut_ranges","captions","caption","caption_style"):
        return None
    result=clone(p)
    if kind=="transition":
        t={"id":ident(),"left":op["left"],"right":op["right"],"kind":op["kind"],"frames":frame(op["frames"])}
        result["transitions"]=[v for v in result.get("transitions",[]) if v["left"]!=t["left"]]+[t]
        ordered=sorted(p["clips"],key=lambda c:c["start"])
        left_index=next((i for i,c in enumerate(ordered) if c["id"]==t["left"]),-1)
        right_index=next((i for i,c in enumerate(ordered) if c["id"]==t["right"]),-1)
        if left_index<0 or right_index<0:raise ValueError("Select two existing timeline clips.")
        cut=ordered[right_index]["start"];start=cut-t["frames"]//2
        label=f"Add {t['kind']} between clips {left_index+1} and {right_index+1}, {t['frames']} frames, timeline {start/FPS:.2f}–{(start+t['frames'])/FPS:.2f}s. Audio and duration unchanged."
    elif kind=="remove_transition":
        result["transitions"]=[t for t in result.get("transitions",[]) if t["left"]!=op["left"]]
        label="Removed the selected transition."
    elif kind=="cut_ranges":
        ranges=sorted((frame(a),frame(b)) for a,b in op["ranges"])
        if not ranges or any(a<0 or a>=b or b>duration(p) for a,b in ranges) or any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])):
            raise ValueError("Invalid or overlapping removal ranges.")
        def removed_before(t):
            return sum(max(0,min(t,b)-a) for a,b in ranges if a<t)
        result["clips"]=[]
        for c in p["clips"]:
            parts=[(c["start"],c["start"]+c["out"]-c["in"])]
            for a,b in ranges:
                parts=[piece for x,y in parts for piece in ((x,min(y,a)),(max(x,b),y)) if piece[0]<piece[1]]
            for i,(a,b) in enumerate(parts):
                result["clips"].append({**c,"id":c["id"] if i==0 else ident(),"_parent":c["id"],
                    "start":a-removed_before(a),"in":c["in"]+a-c["start"],"out":c["in"]+b-c["start"]})
        remap(p,result)
        old_clips={c["id"]:c for c in p["clips"]}
        touched=set()
        for t in p.get("transitions",[]):
            cut=old_clips[t["right"]]["start"];start=cut-t["frames"]//2;end=start+t["frames"]
            if any(a<end and b>start for a,b in ranges):touched.add(t["id"])
        result["transitions"]=[t for t in result["transitions"] if t["id"] not in touched]
        label="Removed "+", ".join(f"{a/FPS:.2f}–{b/FPS:.2f}s" for a,b in ranges)+". Later clips ripple; transitions intersecting removed ranges are removed; clipped captions are flagged for review."
    elif kind=="captions":
        # Generated captions replace only the explicitly targeted clips.
        ids=set(op["clips"])
        result["captions"]=[c for c in result.get("captions",[]) if c["clip"] not in ids]+clone(op["cues"])
        label=f"Added {len(op['cues'])} editable Roman-script caption cues. Review spelling and timing."
    elif kind=="caption":
        cue=next((c for c in result.get("captions",[]) if c["id"]==op["id"]),None)
        if not cue: raise ValueError("Select a caption.")
        if op.get("delete"):
            result["captions"].remove(cue)
        else:
            for k in ("text","in","out","bold"):
                if k in op: cue[k]=clone(op[k])
            cue["needs_review"]=False
            # Edited text invalidates automatic per-word alignment.
            if "text" in op: cue["words"]=[]
        label="Updated caption "+op["id"][:6]+"."
    else:
        result["caption_style"]={"size":frame(op["size"]),"position":op["position"]}
        label=f"Caption style: {op['size']} px, {op['position']}."
    return result,label

def mapped_cues(p):
    clips={c["id"]:c for c in p["clips"]}
    return sorted(({**cue,"start":clips[cue["clip"]]["start"]+cue["in"]-clips[cue["clip"]]["in"],
                    "end":clips[cue["clip"]]["start"]+cue["out"]-clips[cue["clip"]]["in"]}
                   for cue in p.get("captions",[])),key=lambda c:c["start"])

def ass(p):
    style=p.get("caption_style",{})
    head="[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    head+=f"Style: Default,DejaVu Sans,{style.get('size',54)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,{dict(top=8,middle=5,bottom=2)[style.get('position','bottom')]},100,100,65,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    def stamp(n):
        cs=n*4
        return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"
    for cue in mapped_cues(p):
        bold={w.casefold().strip(".,!?") for w in cue.get("bold",[])}
        words=[]
        for w in cue["text"].split():
            safe=w.replace("\\","/").replace("{","(").replace("}",")")
            words.append(r"{\b1}"+safe+r"{\b0}" if w.casefold().strip(".,!?") in bold else safe)
        head+=f"Dialogue: 0,{stamp(cue['start'])},{stamp(cue['end'])},Default,,0,0,0,,"+" ".join(words)+"\n"
    return head

def srt(p):
    def stamp(n):
        ms=n*40
        return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
    return "\n\n".join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(mapped_cues(p)))+"\n"
