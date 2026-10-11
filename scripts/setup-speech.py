"""Run from the repository or beside the packaged app. Downloads stay in its runtime."""
import os,subprocess,sys
from pathlib import Path
base=Path(__file__).resolve().parent
root=base.parent if base.name=="scripts" else base
folder=(root/"resources"/"speech") if (root/"Vibeflow.exe").exists() else root/"runtime"/"speech"
folder.mkdir(parents=True,exist_ok=True)
python=folder/"python"/"Scripts"/"python.exe"
if not python.exists():subprocess.run([sys.executable,"-m","venv",str(folder/"python")],check=True)
subprocess.run([str(python),"-m","pip","install","--cache-dir",str(folder/"cache"),"faster-whisper==1.2.1","huggingface-hub"],check=True)
env={**os.environ,"HF_HOME":str(folder/"cache"),"HF_HUB_DISABLE_SYMLINKS_WARNING":"1"}
code="from huggingface_hub import snapshot_download;import sys;snapshot_download('Systran/faster-whisper-base',local_dir=sys.argv[1])"
subprocess.run([str(python),"-c",code,str(folder/"model")],env=env,check=True)
print("Local speech ready. Restart Vibeflow. OpenAI is used only for text Romanization.")
