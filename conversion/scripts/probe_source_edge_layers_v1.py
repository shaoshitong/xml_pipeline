"""Read-only original scene plus actual native order, geometry and editing probe."""
from pathlib import Path
import argparse,hashlib,json,sys,time,traceback,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
NATIVE=r'''a=>{const output=[];for(const xml of a){document.body.innerHTML='<div id="layerProbe" style="width:8192px;height:8192px"></div>';const g=new Graph(document.getElementById('layerProbe')),d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();const rows={};for(const c of Object.values(g.model.cells)){const s=g.view.getState(c);if(!s)continue;rows[c.id]=c.edge?{points:s.absolutePoints.map(p=>p?[p.x,p.y]:null),source:c.source?.id||null,target:c.target?.id||null}:{box:[s.x,s.y,s.width,s.height]};}output.push(rows);g.destroy();}return output}'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--record',type=Path,required=True);p.add_argument('--work',type=Path,required=True);args=p.parse_args();work=args.work;work.mkdir(parents=True,exist_ok=False);start=time.monotonic();out=dict(new_normal_calls=0,new_QA_calls=0,goal_complete=False)
 try:
  import compiler_svg_scene_frontend_v13 as frontend
  import compiler_svg_general_guard_v9 as core
  from native_svg_screen_offset_v1 import observe,transform
  from svg_source_edge_layers_v1 import repair
  from playwright.sync_api import sync_playwright
  from portable_native_fonts import ready_page
  from native_free_edges_v4 import validate_report
  record=json.loads(args.record.read_bytes());original=(R/record['code_file']).read_text();assert hashlib.sha256(original.encode()).hexdigest()==record['code_sha256'];prepared=frontend.prepare_source(record);assert prepared['ok'];dom=prepared['capture']['dom'];size=prepared['size'];frame=observe(original);canonical=transform(original,frame['offsets'],1)
  repaired,proof=repair(dom,canonical,size);patched=transform(repaired,frame['offsets'],-1);(work/'candidate.drawio').write_text(patched);(work/'source_layer_proof.json').write_text(json.dumps(proof,indent=2));out['source_layer_proof']=proof
  with sync_playwright()as p:
   browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
   try:
    page=ready_page(browser);states=page.evaluate(NATIVE,[original,patched]);assert states[0].keys()==states[1].keys();errors=[]
    for key,before in states[0].items():
     after=states[1][key]
     if'box'in before:
      if any(abs(a-b)>1e-6 for a,b in zip(before['box'],after['box'])):errors.append(dict(id=key,kind='vertex'))
     elif before!=after:
      if before['source']!=after['source']or before['target']!=after['target']or len(before['points'])!=len(after['points'])or any(a is None and b is not None or a is not None and b is None or a is not None and any(abs(x-y)>1e-6 for x,y in zip(a,b))for a,b in zip(before['points'],after['points'])):errors.append(dict(id=key,kind='edge'))
    assert not errors,errors;out['actual_native_vertex_and_edge_states_unchanged']=True
    edits=page.evaluate((S/'compiler_svg_explicit_coordinates_v5.js').read_text(),patched);validate_report(edits);(work/'actual_native_editing.json').write_text(json.dumps(edits));out['actual_native_editing_passed']=True
   finally:browser.close()
  order=core.paint_order(dom,patched,size);(work/'paint_order.json').write_text(json.dumps(order,indent=2));out['actual_native_order']=order
  result=frontend._native(patched,size);(work/'candidate.png').write_bytes(result['png']);(work/'native_render.json').write_text(json.dumps(result['native_render']));out.update(ok=order['ok'],id=record['id'],source_prepared_work=str(prepared['work']),source_code_sha256=record['source_code_sha256'],candidate_sha256=hashlib.sha256(patched.encode()).hexdigest(),normal_conversion_or_acceptance_claimed=False)
 except Exception as error:out.update(ok=False,error=str(error),traceback=traceback.format_exc())
 out['elapsed_seconds']=time.monotonic()-start;(work/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
if __name__=='__main__':main()
