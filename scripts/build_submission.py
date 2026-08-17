from pathlib import Path
import tarfile, py_compile

ROOT=Path(__file__).resolve().parents[1]
SUB=ROOT/'submission'
OUT=ROOT/'artifacts'/'submission_v2.tar.gz'
files=['main.py','predictive_agent.py','parametric_agent.py','base_controller.py','runtime_model.py','meta_runtime.py','learned_model.json']
for f in files:
    p=SUB/f
    if not p.exists(): raise FileNotFoundError(p)
    if p.suffix=='.py': py_compile.compile(str(p),doraise=True)
OUT.parent.mkdir(exist_ok=True)
with tarfile.open(OUT,'w:gz') as tar:
    for f in files: tar.add(SUB/f,arcname=f)
print(OUT)
print('bytes',OUT.stat().st_size)
