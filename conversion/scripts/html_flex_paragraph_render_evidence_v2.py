"""Same-case, exact XML/runtime/assets/font/policy-bound full render evidence.

Geometry-only observations cannot enter the full evidence reuse path. QA builds
its own fresh source/model and receipts in an independent case directory.
"""
import hashlib,json,time,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
PROFILE='official_HTML_paragraph_full_native_observation_v9_same_case_v2'
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(d):return(json.dumps(d,sort_keys=True,ensure_ascii=False)+'\n').encode()
def policy():
 paths=[Path(__file__),W/'scripts/html_source_paragraph_render_v9.py',W/'rendering_html_source_paragraph_v9/remote_render.py',W/'scripts/html_source_paragraph_native_observer_v1.py',W/'scripts/html_source_text_node_binding_v9.py',W/'scripts/compiler_native_text_node_cdp_v2.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json',W/'rendering_html_source_paragraph_v9/assets/viewer-static.min.js']
 from compiler_html_source_flex_paragraph_quality_ro_v2 import pins
 return {**pins(),**{str(p.resolve()):sha(p.read_bytes())for p in paths}}
def dependencies(xml,info,extra_physical_fonts=()):
 from portable_native_fonts import catalog
 cat=catalog();physical={}
 observed=[f for row in info.get('actual_platform_font_usage',[])for f in row.get('fonts',[])]
 names={f['postScriptName']for f in observed if f.get('glyphCount')and not f.get('isCustomFont')}|set(extra_physical_fonts)
 for name in sorted(names):
  matches={(sha(Path(p).read_bytes()),index):(p,index)for p,index in cat.get(name,[])}
  if len(matches)!=1:raise ValueError('render_evidence_physical_font_not_unique:'+name)
  (digest,index),(path,_)=next(iter(matches.items()));physical[name]={'file':path,'collection_index':index,'sha256':digest}
 root=E.fromstring(xml);m=root.find('.//mxGraphModel');assets=[m.get('extFonts','')]+[c.get('style','')for c in root.iter('mxCell')if'image='in c.get('style','')]
 return {'physical_system_font_files':physical,'fontconfig_catalog_sha256':sha(raw(dict(cat))),'embedded_image_and_font_URI_serializations_sha256':sha(raw(assets))}
def render_full(xml,size,work,font_inventory=()):
 from html_source_paragraph_render_v9 import run
 started=time.monotonic();out=run(xml,size,work);directory=Path(out['raw_render_directory']);info=out['native_render'];inputfile=directory/'input_source.drawio'
 assert inputfile.read_bytes()==xml.encode(),'full_render_original_XML_changed'
 identity={'profile':PROFILE,'xml_sha256':sha(xml.encode()),'size':list(size),'png_sha256':sha(out['png']),'raw_directory':str(directory.resolve()),'policy_pins':policy(),'source_primary_metric_physical_fonts':sorted(set(font_inventory)),'dependencies':dependencies(xml,info,font_inventory),'selected_image':info.get('selected_image'),'native_render_file_sha256':sha((directory/'native_render.json').read_bytes()),'viewer_bundle_sha256':info['viewer_bundle_sha256']}
 (directory/'exact_full_render_identity.json').write_bytes(raw(identity));out['exact_full_render_identity']=identity
 frames=1+int('outside_page_pixel_audit'in info)+int('tight_diagnostic'in info)+2*int('source_html_export'in info)
 (directory/'performance.json').write_bytes(raw({'phase':'full_native_render','wall_monotonic_seconds':time.monotonic()-started,'screenshot_count_from_executed_branch_receipts':frames,'xml_sha256':identity['xml_sha256'],'png_sha256':identity['png_sha256'],'profile':PROFILE,'reused':False}))
 return out
def reuse_full(xml,size,out,case_root,receipt):
 started=time.monotonic();assert 'exact_full_render_identity'in out,'render_evidence_full_profile_required';identity=out['exact_full_render_identity'];directory=Path(identity['raw_directory']).resolve(strict=True);case_root=Path(case_root).resolve(strict=True)
 assert directory.is_relative_to(case_root),'render_evidence_cross_case_reuse_forbidden'
 assert json.loads((directory/'exact_full_render_identity.json').read_bytes())==identity,'render_evidence_receipt_changed'
 assert identity['profile']==PROFILE and identity['policy_pins']==policy(),'render_evidence_profile_or_runtime_policy_changed'
 assert identity['xml_sha256']==sha(xml.encode())and identity['size']==list(size),'render_evidence_XML_or_canvas_changed'
 assert(directory/'input_source.drawio').read_bytes()==xml.encode(),'render_evidence_input_file_changed'
 assert identity['png_sha256']==sha(out['png'])==sha((directory/'render.png').read_bytes()),'render_evidence_actual_PNG_changed'
 assert identity['native_render_file_sha256']==sha((directory/'native_render.json').read_bytes()),'render_evidence_actual_metadata_changed'
 assert json.loads((directory/'native_render.json').read_bytes())==out['native_render'],'render_evidence_metadata_not_actual_receipt'
 assert identity['dependencies']==dependencies(xml,out['native_render'],identity['source_primary_metric_physical_fonts']),'render_evidence_font_or_image_asset_changed'
 assert identity['selected_image']=='declared_first_page','render_evidence_requires_complete_native_model_frame'
 process=json.loads((directory/'owned_process.json').read_bytes());assert process['ok']and process['cleanup_complete'],'render_evidence_incomplete_owned_process'
 proof={'verified':True,'same_case':str(case_root),'source_render_identity':identity,'actual_new_render_calls':0,'actual_new_screenshots':0,'verification_monotonic_seconds':time.monotonic()-started}
 Path(receipt).write_bytes(raw(proof));return out
