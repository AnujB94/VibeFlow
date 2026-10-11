import json,winreg
from pathlib import Path
p=Path("verification/report.json")
report=json.loads(p.read_text())
key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
report["machine"]["processor"]=winreg.QueryValueEx(key,"ProcessorNameString")[0].strip()
report["machine"]["gpu_acceleration"]="not used; software libx264"
gpu=[]
try:
    key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SYSTEM\CurrentControlSet\Control\Video")
    for i in range(winreg.QueryInfoKey(key)[0]):
        child=winreg.EnumKey(key,i)
        try:
            sub=winreg.OpenKey(key,child+r"\0000")
            name=winreg.QueryValueEx(sub,"DriverDesc")[0]
            if name not in gpu:gpu.append(name)
        except OSError:pass
except OSError:pass
report["machine"]["display_adapters"]=gpu
p.write_text(json.dumps(report,indent=2),"utf-8")
print(json.dumps(report["machine"],indent=2))
