"""Real, nonpublishing paint-aware marker fit with unchanged fixed gate."""
import copy,hashlib,json,uuid,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,now,native
from tikz_execution_binding_v2 import marker_metrics
from tikz_execution_binding_v2_pilot import allowed_delta
from tikz_execution_marker_paint_fit import fit_painted_markers,aa_diagnostics
from svg_convert_v3 import unpack,pack
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
 pilot=json.loads((W/'tikz_execution_binding_pilot.json').read_text());assert pilot['ok'];folder=R/pilot['work'];xml=(folder/'candidate.drawio').read_text();record=json.loads((folder/'baseline_record.json').read_text());before=(folder/'baseline.png').read_bytes();bound=(folder/'candidate.png').read_bytes();dom=json.loads((folder/'source_dom.json').read_text());width,height=Image.open(R/record['original_reference']).size;assert sha(xml.encode())==pilot['output_code_sha256'];assert sha(before)==record['image_sha256']
 work=W/'tikz_execution_marker_paint_pilot'/pilot['id']/uuid.uuid4().hex[:12];work.mkdir(parents=True);oldquality=marker_metrics(before,bound,xml,dom,pilot['binding']);out={'at':now(),'id':pilot['id'],'work':str(work.relative_to(R)),'published':False,'v1_actual_aa_diagnostics':aa_diagnostics(before,bound,dom,pilot['binding'],oldquality),'candidates':[]}
 for rank in range(4):
  candidate,binding,fit=fit_painted_markers(xml,dom,pilot['binding'],R/'evaluation/assets/viewer-static.min.js',rank);delta=allowed_delta(xml,candidate);(work/f'rank{rank}.drawio').write_text(candidate);fresh=native.native_job(candidate,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');entry={'rank':rank,'render_ok':fresh['ok'],'fitting':fit,'allowed_delta':delta,'code_sha256':sha(candidate.encode())}
  if fresh['ok']:
   png=fresh['png'];(work/f'rank{rank}.png').write_bytes(png);quality=marker_metrics(before,png,candidate,dom,binding);entry.update(quality=quality,aa_diagnostics=aa_diagnostics(before,png,dom,binding,quality),png_sha256=sha(png));print(json.dumps({'rank':rank,'ok':quality['ok'],'outside':quality['changed_pixels_outside_marker_rois'],'boundary':[m['v2_symmetric_boundary_distance_device_px'] for m in quality['markers']],'core':[(m['alpha_levels'][2]['symmetric_boundary_max_device_px'],m['alpha_levels'][2]['symmetric_boundary_p95_device_px']) for m in entry['aa_diagnostics']['markers']]}),flush=True)
   if quality['ok']:
    from auto_quality_move import audit
    moves=audit(candidate);assert len(moves['moves'])==16;assert all(abs(m['delta']['x']-17)<.05 and abs(m['delta']['y']-11)<.05 for m in moves['moves']);(work/'candidate.drawio').write_text(candidate);(work/'candidate.png').write_bytes(png);(work/'binding.json').write_text(json.dumps(binding,indent=2)+'\n');(work/'native_moves.json').write_text(json.dumps(moves,indent=2)+'\n');entry['actual_endpoint_moves']=len(moves['moves']);out.update(ok=True,chosen_rank=rank)
  out['candidates'].append(entry)
  if out.get('ok'):break
 out.setdefault('ok',False)
 if out['ok']:
  negatives=[];marker=binding['binding']['native_arrowheads'][0]
  for name in ('missing_head','tiny_head','reversed_head','wrong_tip','wrong_color'):
   root=E.fromstring(candidate);edge=next(c for c in root.iter('mxCell') if c.get('id')==marker['edge']);style=unpack(edge.get('style'));side=marker['side']
   if name=='missing_head':style[side+'Arrow']='none'
   if name=='tiny_head':style[side+'Size']='0.1'
   if name=='reversed_head':
    # Swap the real bound connector orientation; do not merely relabel proof.
    source,target=edge.get('source'),edge.get('target');edge.set('source',target);edge.set('target',source)
    for suffix in ('X','Y','Perimeter'):style['exit'+suffix],style['entry'+suffix]=style['entry'+suffix],style['exit'+suffix]
   if name=='wrong_tip':style['entryX']=str(float(style['entryX'])+.1)
   if name=='wrong_color':style[side+'FillColor']='#ff0000';style[side+'StrokeColor']='#ff0000'
   edge.set('style',pack(style));bad=E.tostring(root,encoding='unicode');render=native.native_job(bad,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];q=marker_metrics(before,render['png'],bad,dom,binding);assert not q['ok'],name;negatives.append({'case':name,'rejected':True,'quality':q});print(json.dumps({'negative':name,'rejected':True}),flush=True)
  out['actual_native_negative_fixtures']=negatives
 assert (folder/'candidate.drawio').read_text()==xml and sha((R/record['code_file']).read_bytes())==record['code_sha256'];out['v1_draft_and_canonical_unchanged']=True
 (work/'report.json').write_text(json.dumps(out,indent=2)+'\n');(W/'tikz_execution_marker_paint_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'ok':out['ok'],'work':out['work'],'published':False}),flush=True)


if __name__=='__main__':main()
