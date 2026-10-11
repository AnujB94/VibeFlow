"""Local RMS pause analysis with strict threshold qualification before padding."""
import array
import math
import wave
from backend.project import FPS, duration

def quiet_ranges(samples, rate, threshold=1.0, padding=.12, db=-38):
    if not .1 <= threshold <= 30 or not 0 <= padding <= 1 or not -70 <= db <= -15:
        raise ValueError("Pause settings are outside the supported range.")
    block=max(1,round(rate*.01)); limit=32768*10**(db/20)
    spans=[]; start=None
    for a in range(0,len(samples),block):
        values=samples[a:a+block]
        quiet=math.sqrt(sum(v*v for v in values)/len(values))<=limit
        if quiet and start is None: start=a
        if not quiet and start is not None:
            spans.append((start,a));start=None
    if start is not None: spans.append((start,len(samples)))
    output=[]
    for a,b in spans:
        if (b-a) > threshold*rate + .5:
            x,y=math.ceil((a/rate+padding)*FPS-1e-8),math.floor((b/rate-padding)*FPS+1e-8)
            if x<y: output.append([x,y])
    return output

def find_pauses(media,p,job,folder,threshold=1,padding=.12,db=-38):
    assets={m["id"]:m for m in p["media"]};ranges=[];cursor=0;timeline=array.array("h")
    for i,c in enumerate(sorted(p["clips"],key=lambda c:c["start"])):
        if c["start"]>cursor and (c["start"]-cursor)/FPS>threshold:
            ranges.append([cursor,c["start"]])
        timeline.extend(array.array("h",[0])*((c["start"]-cursor)*640))
        n=c["out"]-c["in"];tmp=folder/(job["id"]+f"-{i}.wav")
        try:
            media.execute(["-ss",c["in"]/FPS,"-t",n/FPS,"-i",assets[c["source"]]["working"],
                           "-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",tmp],job,n/FPS)
            with wave.open(str(tmp),"rb") as wav: values=array.array("h",wav.readframes(wav.getnframes()))
            expected=n*640
            timeline.extend(values[:expected])
            if len(values)<expected:timeline.extend(array.array("h",[0])*(expected-len(values)))
        finally: tmp.unlink(missing_ok=True)
        cursor=c["start"]+n
    ranges += quiet_ranges(timeline,16000,threshold,padding,db)
    # Merge touching intervals, never invent removal across speech.
    result=[]
    for a,b in sorted(ranges):
        b=min(b,duration(p))
        if result and a<=result[-1][1]:result[-1][1]=max(b,result[-1][1])
        elif a<b:result.append([a,b])
    return result
