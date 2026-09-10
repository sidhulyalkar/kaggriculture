from __future__ import annotations
import ast,base64,hashlib,json,pathlib,urllib.request,zlib
REF='raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta'
EXPECTED={'c92':'7b13e69371509fe53f1dbb7b769d73f6c82ff41db37df7a9a3a1879e82ed82f2','c94':'7b0e5a7b9d18dc583f5789e50a54dca43561f6d08c1c616b4219bf50bcb8311f','c95':'489f5d197527f107027626cce79d850fd2ca90edd43d94384b849b6511e27bdb'}
CLOCK='''\n\n# canonical clock hardening\n_V93_HOST=agent\ndef agent(obs,config=None):\n    if obs.get("step") is None:\n        obs=dict(obs); obs["step"]=int(obs.get("day",0) or 0)*24+int(obs.get("hour",0) or 0)\n    return _V93_HOST(obs,config)\ndef v93_submission_agent(obs,config=None): return agent(obs,config)\n'''
def pull():
 req=urllib.request.Request(f'https://www.kaggle.com/api/v1/kernels/pull/{REF}',headers={'User-Agent':'Mozilla/5.0 V93'})
 with urllib.request.urlopen(req,timeout=90) as r:o=json.load(r)
 return json.loads(o['blob']['source'])
def text(c):
 s=c.get('source','');return ''.join(s) if isinstance(s,list) else str(s)
def candidates(nb):
 for c in nb['cells']:
  s=text(c)
  if '_AGENT_B64_PARTS' not in s and '_C95_AGENT_B64_PARTS' not in s:continue
  try:t=ast.parse(s)
  except:continue
  for n in t.body:
   if not isinstance(n,ast.Assign):continue
   for x in n.targets:
    if isinstance(x,ast.Name) and x.id in ('_AGENT_B64_PARTS','_C95_AGENT_B64_PARTS'):
     try:p=ast.literal_eval(n.value);raw=zlib.decompress(base64.b64decode(''.join(p)));yield raw
     except:pass
def main():
 root=pathlib.Path('experiments/v93/generated');root.mkdir(parents=True,exist_ok=True);found={}
 bysha={v:k for k,v in EXPECTED.items()}
 for raw in candidates(pull()):
  sha=hashlib.sha256(raw).hexdigest();name=bysha.get(sha)
  if not name:continue
  src=raw.decode()+CLOCK;d=root/name;d.mkdir(exist_ok=True);(d/'main.py').write_text(src);compile(src,name,'exec');found[name]=sha
 print(found)
 if set(found)!=set(EXPECTED):raise SystemExit(f'missing {set(EXPECTED)-set(found)}')
 (root/'manifest.json').write_text(json.dumps(found,indent=2)+'\n')
if __name__=='__main__':main()
