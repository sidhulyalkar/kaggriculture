from pathlib import Path
import hashlib, tarfile, tempfile

ROOT=Path(__file__).resolve().parents[1]
SUB=ROOT/'submission';OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True)
FILES=['guarded_market_agent.py','adaptive_market_agent.py','market_predictor.py','market_flow_runtime.py','predictive_agent.py','parametric_agent.py','base_controller.py','runtime_model.py','meta_runtime.py','learned_model.json','adaptive_market_model.json']

def build(mode):
    fn='safe_agent' if mode=='safe' else 'balanced_agent'
    out=OUT/f'submission_v56_{mode}.tar.gz'
    main=f"from guarded_market_agent import {fn} as _agent\n\ndef agent(observation, configuration=None):\n    return _agent(observation, configuration)\n"
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'main.py';p.write_text(main,encoding='utf-8')
        with tarfile.open(out,'w:gz') as tf:
            tf.add(p,arcname='main.py')
            for name in FILES:
                src=SUB/name
                if not src.exists():raise FileNotFoundError(src)
                tf.add(src,arcname=name)
    digest=hashlib.sha256(out.read_bytes()).hexdigest();print(mode,out,out.stat().st_size,digest);return out

if __name__=='__main__':
    build('safe');build('balanced')
