from pathlib import Path
import py_compile
import tarfile

ROOT=Path(__file__).resolve().parents[1];SUB=ROOT/"submission";OUT=ROOT/"artifacts"/"submission_v55_adaptive.tar.gz"
files={
    "main.py":"adaptive_main.py",
    "adaptive_market_agent.py":"adaptive_market_agent.py",
    "market_predictor.py":"market_predictor.py",
    "market_flow_runtime.py":"market_flow_runtime.py",
    "predictive_agent.py":"predictive_agent.py",
    "parametric_agent.py":"parametric_agent.py",
    "base_controller.py":"base_controller.py",
    "runtime_model.py":"runtime_model.py",
    "meta_runtime.py":"meta_runtime.py",
    "learned_model.json":"learned_model.json",
    "adaptive_market_model.json":"adaptive_market_model.json",
}
for src in files.values():
    p=SUB/src
    if not p.exists():raise FileNotFoundError(p)
    if p.suffix==".py":py_compile.compile(str(p),doraise=True)
OUT.parent.mkdir(exist_ok=True)
with tarfile.open(OUT,"w:gz") as tar:
    for arc,src in files.items():tar.add(SUB/src,arcname=arc)
print(OUT);print("bytes",OUT.stat().st_size)
