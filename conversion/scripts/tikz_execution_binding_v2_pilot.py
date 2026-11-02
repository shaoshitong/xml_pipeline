"""Nonpublishing native marker fit on the unchanged real v1 bound draft."""
import copy,hashlib,json,uuid,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now,native
from svg_convert_v3 import unpack
from tikz_execution_binding_v2 import VIEWER_SHA256,TYPES,native_marker_polygon,fit_native_markers,marker_metrics
sha=lambda b:hashlib.sha256(b).hexdigest()


def factory_parity():
 runtime=R/'evaluation/assets/viewer-static.min.js';assert sha(runtime.read_bytes())==VIEWER_SHA256
 cases=[{'kind':kind,'size':size,'stroke':sw,'point':[41.2,-3.7],'unit':u} for kind in TYPES for size in (2.,7.25,19.) for sw in (.4,1.7,3.5) for u in ([1.,0.],[0.,-1.],[.6,.8])]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(runtime))
   actual=page.evaluate(r'''cases=>cases.map(c=>{let points=[];const canvas={begin(){},moveTo(x,y){points.push([x,y])},lineTo(x,y){points.push([x,y])},close(){},fillAndStroke(){},stroke(){}};const end=new mxPoint(...c.point);mxMarker.createMarker(canvas,{},c.kind,end,...c.unit,c.size,false,c.stroke,true)();return {points,end:[end.x,end.y]}})''',cases)
  finally:browser.close()
 maximum=0.
 for case,got in zip(cases,actual):
  points,end=native_marker_polygon(case['kind'],case['size'],case['stroke'],case['point'],case['unit']);assert len(points)==len(got['points'])
  maximum=max(maximum,max(abs(a-b) for p,q in zip(points,got['points']) for a,b in zip(p,q)),max(abs(a-b) for a,b in zip(end,got['end'])))
 assert maximum<1e-10
 return {'ok':True,'actual_viewer_sha256':VIEWER_SHA256,'cases':len(cases),'max_coordinate_error':maximum,'actual_canvas_factory_tested':True}


def allowed_delta(before,after):
 old={c.get('id'):c for c in E.fromstring(before).iter('mxCell')};new={c.get('id'):c for c in E.fromstring(after).iter('mxCell')};assert set(old)==set(new)
 allowed={side+suffix for side in ('start','end') for suffix in ('Arrow','Size')}|{prefix+suffix for prefix in ('entry','exit') for suffix in ('X','Y','Perimeter')};changed={}
 for id in old:
  a,b=copy.deepcopy(old[id]),copy.deepcopy(new[id]);sa,sb=unpack(a.attrib.pop('style','')),unpack(b.attrib.pop('style',''));assert E.tostring(a)==E.tostring(b),'Nonstyle object changed '+id
  diff={k:[sa.get(k),sb.get(k)] for k in sa.keys()|sb.keys() if sa.get(k)!=sb.get(k)}
  assert set(diff)<=allowed,'Nonmarker style changed '+id
  if diff:assert old[id].get('edge')=='1';changed[id]=diff
 return {'ok':True,'changed_edges':changed,'only_marker_type_size_and_port_styles':True}


def main():
 report=json.loads((W/'tikz_execution_binding_pilot.json').read_text());assert report['ok'];folder=R/report['work'];base=(folder/'baseline.drawio').read_text();xml=(folder/'candidate.drawio').read_text();dom=json.loads((folder/'source_dom.json').read_text());record=json.loads((folder/'baseline_record.json').read_text());original_before=(folder/'baseline.png').read_bytes();bound_before=(folder/'candidate.png').read_bytes();width,height=Image.open(R/record['original_reference']).size
 assert sha(base.encode())==record['code_sha256'] and sha(xml.encode())==report['output_code_sha256'];assert sha(original_before)==record['image_sha256'] and sha(bound_before)==report['output_image_sha256']
 work=W/'tikz_execution_binding_v2_pilot'/report['id']/uuid.uuid4().hex[:12];work.mkdir(parents=True)
 out={'at':now(),'id':report['id'],'work':str(work.relative_to(R)),'published':False,'v1_draft_unchanged':True,'factory_parity':factory_parity(),'v1_scale_metrics':marker_metrics(original_before,bound_before,xml,dom,report['binding']),'candidates':[]}
 for rank in range(4):
  candidate,binding,fitting=fit_native_markers(xml,dom,report['binding'],rank=rank);delta=allowed_delta(xml,candidate);(work/f'rank{rank}.drawio').write_text(candidate)
  fresh=native.native_job(candidate,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');entry={'rank':rank,'render_ok':fresh['ok'],'fitting':fitting,'allowed_delta':delta,'code_sha256':sha(candidate.encode())}
  if fresh['ok']:
   png=fresh['png'];(work/f'rank{rank}.png').write_bytes(png);quality=marker_metrics(original_before,png,candidate,dom,binding);entry.update(png_sha256=sha(png),quality=quality)
   if quality['ok']:
    from auto_quality_move import audit
    moves=audit(candidate);assert len(moves['moves'])==16
    assert all(abs(move['delta']['x']-17)<.05 and abs(move['delta']['y']-11)<.05 for move in moves['moves']);entry['actual_endpoint_moves']=len(moves['moves']);(work/'candidate.drawio').write_text(candidate);(work/'candidate.png').write_bytes(png);(work/'binding.json').write_text(json.dumps(binding,indent=2)+'\n');(work/'native_moves.json').write_text(json.dumps(moves,indent=2)+'\n');out['chosen_rank']=rank;out['ok']=True
  out['candidates'].append(entry)
  if out.get('ok'):break
 assert (folder/'candidate.drawio').read_text()==xml and sha((R/record['code_file']).read_bytes())==record['code_sha256'];out.setdefault('ok',False)
 (work/'report.json').write_text(json.dumps(out,indent=2)+'\n');(W/'tikz_execution_binding_v2_pilot.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out))

if __name__=='__main__':main()
