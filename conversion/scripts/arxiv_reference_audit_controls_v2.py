"""Actual native-rendered corruptions; no fixture is published as dataset data."""
from pathlib import Path
import base64,copy,hashlib,html,json,os,re,shutil,sys,time,uuid,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env'),str(R/'evaluation/assets/pdf_inventory_python_v1')]
import arxiv_native_reference_audit_v2 as qa
from arxiv_sourceonly_bulk_200_v1_1 import models
from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
from PIL import Image
sha=lambda b:hashlib.sha256(b).hexdigest()
P=qa.base.P;D=P/'original_PDF_reference_audit_v2';work=D/'controls'/uuid.uuid4().hex;work.mkdir(parents=True)
rows=qa.base.snapshot();positive_ids=['5fa7742932940a338eb2e269c491739b4c1eb1dc25fd3d53de978afbed899fa8',
 '9a88805a68cdaa4e29150d799ffd2d9c4927023f5b949e37d877e9307d045192',
 'fa30e2715399383435e1cbe14cb8ebe563f70a52be79a8a39fad89616972f747']
auditor=qa.Auditor();renderer=None;positive=[];negative=[]
try:
 for ident in positive_ids:
  result=auditor.audit(rows[ident],work/'positive'/ident)
  positive.append({'id':ident,'status':result['status'],'audit':str((work/'positive'/ident/'audit.json').relative_to(R))})
  assert result['status']=='qualified_registered_original_PDF_visual_profile_v2',positive[-1]
 original=rows[positive_ids[-1]];source_code=(R/original['author_xml_file']).read_text();model=models(source_code)[0]
 auditor.close();auditor.renderer=None
 for kind in ['remove_original_long_label','move_original_image','whole_figure_image_wrapper']:
  folder=work/'negative'/kind;folder.mkdir(parents=True)
  root=copy.deepcopy(model)
  if kind=='remove_original_long_label':
   cells=[c for c in root.iter('mxCell') if c.get('vertex')=='1' and c.get('value') and 'shape=image' not in c.get('style','')]
   target=max(cells,key=lambda c:len(html.unescape(re.sub('<[^>]*>','',c.get('value','')))));target.set('value','')
  elif kind=='move_original_image':
   target=next(c for c in root.iter('mxCell') if 'shape=image' in c.get('style',''))
   geometry=target.find('mxGeometry');geometry.set('x',str(float(geometry.get('x','0'))+100));geometry.set('y',str(float(geometry.get('y','0'))+50))
  else:
   root=ET.Element('mxGraphModel');cells=ET.SubElement(root,'root');ET.SubElement(cells,'mxCell',id='0');ET.SubElement(cells,'mxCell',id='1',parent='0')
   uri='data:image/png,'+base64.b64encode((R/original['image_file']).read_bytes()).decode()
   cell=ET.SubElement(cells,'mxCell',id='wrapper',parent='1',vertex='1',style='shape=image;image='+uri+';imageAspect=0;')
   with Image.open(R/original['image_file']) as im:w,h=im.size
   ET.SubElement(cell,'mxGeometry',x='0',y='0',width=str(w),height=str(h),**{'as':'geometry'})
  xml=ET.tostring(root,encoding='unicode');code=folder/'corrupted.drawio';code.write_text(xml)
  # The actual official renderer produces the corrupted pixels. A hash-only
  # change cannot satisfy these controls.
  rendered=folder/'rendered';render_error=None
  renderer=OfficialXmlPng()
  try:renderer.render(xml,rendered,{})
  except Exception as e:render_error=type(e).__name__+':'+str(e)
  finally:renderer.close();renderer=None
  image=rendered/'official.png'
  assert image.exists(),'negative fixture had no actual native render'
  with Image.open(image) as a,Image.open(R/original['image_file']) as b:
   pixels_changed=a.size!=b.size or a.convert('RGBA').tobytes()!=b.convert('RGBA').tobytes()
  if kind!='whole_figure_image_wrapper':assert pixels_changed,'negative fixture must visibly alter real pixels'
  source_pdf=(R/original['render_edit_evidence']).parent/'source.pdf';shutil.copyfile(source_pdf,rendered/'source.pdf')
  # Deliberately inconsistent fixture hypothesis: changed native XML/PNG versus
  # the unchanged real source PDF. It is isolated from every once/data ledger.
  candidate={**original,'author_xml_file':str(code.relative_to(R)),'author_xml_sha256':sha(code.read_bytes()),
   'image_file':str(image.relative_to(R)),'image_sha256':sha(image.read_bytes()),
   'render_edit_evidence':str((rendered/'render_edit_evidence.json').relative_to(R))}
  result=auditor.audit(candidate,folder/'independent_audit')
  auditor.close();auditor.renderer=None
  assert not result['status'].startswith('qualified_'),(kind,result)
  negative.append({'kind':kind,'actual_native_pixels_changed':pixels_changed,'render_error':render_error,
    'rejected_status':result['status'],'reason':result.get('reason'),'raster_failures':result.get('strong_original_reference_raster_gate',{}).get('failures'),
    'audit':str((folder/'independent_audit/audit.json').relative_to(R))})
finally:
 auditor.close()
 if renderer:renderer.close()
pins={str(p.relative_to(R)):sha(p.read_bytes()) for p in [R/'conversion/scripts/arxiv_native_reference_audit_v1.py',
 R/'conversion/scripts/arxiv_native_reference_audit_v2.py',R/'conversion/scripts/arxiv_reference_audit_controls_v2.py',
 R/'conversion/scripts/arxiv_bulk_official_xml_png_v1.py',R/'conversion/scripts/auto_quality_common.py']}
proof={'schema':'arxiv_original_reference_audit_real_controls_v2','positive':positive,'negative':negative,
 'positive_passed':len(positive),'actual_negative_rejected':len(negative),'false_accepts':0,'pins':pins,
 'fixture_only_no_dataset_publication':True,'normal_generations':0,'official_PDF_import_calls':0,'external_models':0}
qa.base.write_json(work/'proof.json',proof);qa.base.write_json(D/'controls_latest.json',{'proof':str((work/'proof.json').relative_to(R)),'proof_sha256':sha((work/'proof.json').read_bytes())})
print(json.dumps({'proof':str(work/'proof.json'),'positive':len(positive),'actual_negative_rejected':len(negative),'false_accepts':0,'negative_results':negative},ensure_ascii=True),flush=True)
