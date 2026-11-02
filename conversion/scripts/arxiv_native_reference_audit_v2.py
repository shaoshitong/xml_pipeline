"""Well-conditioned geometric registration; all original raster gates unchanged."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env')]
import arxiv_native_reference_audit_v1 as base
from arxiv_sourceonly_bulk_200_v1_1 import facts

original_registration=base.registration
def stable_registration(anchors):
 # SVG exports round small icon dimensions; using one 20px icon to calibrate a
 # 2000px canvas amplifies that rounding. Prefer the best-conditioned declared
 # geometry, using no pixel comparison and retaining every independent check.
 def order(a):
  b=a['native'];w,h=b[2]-b[0],b[3]-b[1]
  return (-min(w,h),-w*h,a['kind'],repr(a['identity']))
 result=original_registration(sorted(anchors,key=order))
 result['registration_rule']='Largest minimum-side source geometry, then area/identity; every other independent anchor validates the one transform. No raster-score fitting.'
 return result
base.registration=stable_registration

class Auditor(base.Auditor):
 def audit(self,record,folder):
  authority=None
  for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
   with sqlite3.connect((base.P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True) as db:
    row=db.execute('select record from pdfs where id=? and status=?',(record['id'],'qualified_native_xml_png_pair')).fetchone()
   if row:authority=json.loads(row[0]);break
  if authority is None or any(record.get(k)!=authority.get(k) for k in ['author_xml_sha256','image_sha256']):
   folder.mkdir(parents=True,exist_ok=True)
   result={'id':record['id'],'status':'rejected_source_authority_binding_changed','reason':'Candidate XML/PNG does not match the existing official PDF once-ledger authority.',
           'normal_generation_calls':0,'external_models':0,'seconds':0}
   base.write_json(folder/'audit.json',result);return result
  structure=facts((R/record['author_xml_file']).read_text())
  if structure['pages']!=1 or structure['all_single_image_wrapper'] or not structure['complexity_match']:
   folder.mkdir(parents=True,exist_ok=True)
   result={'id':record['id'],'status':'rejected_noncomplex_or_whole_figure_wrapper','normal_generation_calls':0,'external_models':0,'seconds':0,'structure':structure}
   base.write_json(folder/'audit.json',result);return result
  out=super().audit(record,folder)
  if out['status']=='qualified_registered_original_PDF_visual_profile_v1':out['status']='qualified_registered_original_PDF_visual_profile_v2'
  out['registration_profile']='source_geometry_maximum_numerical_support_v2';out['independent_structure']=structure
  base.write_json(folder/'audit.json',out);return out

if __name__=='__main__':
 D=base.P/'original_PDF_reference_audit_v2';D.mkdir(exist_ok=True);auditor=Auditor();rows=base.snapshot();results=[]
 try:
  for ident,row in sorted(rows.items()):
   folder=D/'development'/ident
   if (folder/'audit.json').exists():result=json.loads((folder/'audit.json').read_text())
   else:result=auditor.audit(row,folder)
   results.append(result)
   print(json.dumps({'id':ident,'status':result['status'],'reason':result.get('reason'),'seconds':result['seconds'],'anchors':len(result.get('source_geometry_anchor_inventory',[]))},ensure_ascii=True),flush=True)
 finally:auditor.close()
 summary={'cases':len(results),'states':dict(collections.Counter(x['status'] for x in results)),'external_models':0,'normal_generations':0}
 base.write_json(D/'development_summary.json',summary);print(json.dumps(summary))
