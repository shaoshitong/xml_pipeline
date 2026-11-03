"""Archive provenance must reject tampered, duplicated and escaping sources."""
from pathlib import Path
import io,json,tarfile,tempfile
from arxiv_direct_author_XML_replay_v1 import archive_file
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'source';root.mkdir();f=root/'diagram.drawio';f.write_bytes(b'<mxGraphModel><root/></mxGraphModel>')
 def check(entries):
  data=io.BytesIO()
  with tarfile.open(fileobj=data,mode='w') as t:
   for name,body in entries:
    m=tarfile.TarInfo(name);m.size=len(body);t.addfile(m,io.BytesIO(body))
  data.seek(0)
  with tarfile.open(fileobj=data) as t:return archive_file(t,f,root)
 assert check([('./diagram.drawio',f.read_bytes())])['bytes']==f.stat().st_size
 rejected=[]
 for name,entries in [('tampered',[('diagram.drawio',b'tampered')]),('duplicate',[('diagram.drawio',f.read_bytes()),('./diagram.drawio',f.read_bytes())]),('escaping',[('../diagram.drawio',f.read_bytes())]),('wrong_member',[('another.drawio',f.read_bytes())])]:
  try:check(entries)
  except AssertionError:rejected.append(name)
 assert rejected==['tampered','duplicate','escaping','wrong_member']
 print(json.dumps(dict(exact_archive_member_passed=True,rejected=rejected,external_requests=0,PDF_import_calls=0)))
