import json,sys
from faster_whisper import WhisperModel
model=WhisperModel(sys.argv[3],device="cpu",compute_type="int8",cpu_threads=4)
segments,info=model.transcribe(sys.argv[1],beam_size=5,word_timestamps=True,vad_filter=False)
words=[{"word":w.word,"start":w.start,"end":w.end} for s in segments for w in (s.words or [])]
with open(sys.argv[2],"w",encoding="utf8") as f:json.dump({"words":words,"language":info.language},f,ensure_ascii=False)
