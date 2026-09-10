from __future__ import annotations
import ast,base64,hashlib,json,pathlib,re,urllib.request,zlib
REF='kaitofukami/103-128-fresh-public-v43-sparse-shop-hybrid'
UA={'User-Agent':'Mozilla/5.0 V94-sparse'}
def pull():
 req=urllib.request.Request(f'https://www.kaggle.com/api/v1/kernels/pull/{REF}',headers=UA)
 with urllib.request.urlopen(req,timeout=90) as r:o=json.load(r)
 src=(o.get('blob') or {}).get('source')
 if not src:raise RuntimeError('missing notebook source')
 return json.loads(src)
def text(c):
 s=c.get('source','');return ''.join(s) if isinstance(s,list) else str(s)
def decode_values(src):
 out=[]
 try:t=ast.parse(src)
 except SyntaxError:return out
 for n in ast.walk(t):
  if not isinstance(n,(ast.Assign,ast.AnnAssign)):continue
  ts=n.targets if isinstance(n,ast.Assign) else [n.target]
  names=[x.id for x in ts if isinstance(x,ast.Name)] or ['literal']
  try:v=ast.literal_eval(n.value)
  except:continue
  vals=[]
  if isinstance(v,str):vals=[v]
  elif isinstance(v,(list,tuple)) and v and all(isinstance(x,str) for x in v):vals=[''.join(v)]
  for name in names:
   for s in vals:
    if len(s)<500:continue
    b=s.encode('ascii','ignore')
    for codec,fn in [('b64',lambda x:base64.b64decode(x,validate=False)),('b85',base64.b85decode)]:
     try:d=fn(b)
     except:continue
     for zname,zfn in [('',lambda x:x),('_zlib',zlib.decompress)]:
      try:dd=zfn(d)
      except:continue
      if len(dd)>1000:out.append((name,codec+zname,dd))
 return out
def main():
 root=pathlib.Path('experiments/v94/harvest');root.mkdir(parents=True,exist_ok=True)
 nb=pull();(root/'notebook.ipynb').write_text(json.dumps(nb,indent=1));cells=[text(c) for c in nb.get('cells',[])];(root/'all_code.txt').write_text('\n\n# CELL\n\n'.join(cells))
 seen={}; report=[]
 for i,s in enumerate(cells):
  for name,codec,d in decode_values(s):
   sha=hashlib.sha256(d).hexdigest()
   if sha in seen:continue
   seen[sha]=1
   ext='.py' if d.lstrip().startswith((b'from ',b'import ',b'def ',b'class ',b'#')) else '.bin'
   p=root/f'decoded_c{i}_{re.sub(r"[^A-Za-z0-9_]+","_",name)[:40]}_{codec}{ext}';p.write_bytes(d)
   rec={'path':p.name,'bytes':len(d),'sha256':sha}
   if ext=='.py':
    try:compile(d.decode(),str(p),'exec');rec['compile']=True
    except Exception as e:rec['compile']=False;rec['error']=repr(e)
   report.append(rec)
 # also locate literal writefile-style main source
 for i,s in enumerate(cells):
  if 'def agent' in s and ('main.py' in s or 'submission' in s.lower()) and len(s)>2000:
   clean=re.sub(r'^%%writefile\s+main\.py\s*\n','',s,count=1)
   try:compile(clean,f'cell{i}.py','exec')
   except:continue
   p=root/f'cell{i}_agent.py';p.write_text(clean);report.append({'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'compile':True})
 (root/'report.json').write_text(json.dumps({'ref':REF,'cells':len(cells),'artifacts':report},indent=2)+'\n')
 print(json.dumps({'ref':REF,'cells':len(cells),'artifacts':report},indent=2))
if __name__=='__main__':main()
