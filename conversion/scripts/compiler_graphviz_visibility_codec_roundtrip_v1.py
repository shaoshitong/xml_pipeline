"""Actual upstream model edit/save conservation of nonpainting source metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))

SCRIPT=r'''([xml,key])=>{
 document.body.innerHTML='<div id="constraintMetadataGraph" style="width:8192px;height:8192px"></div>';
 const graph=new Graph(document.getElementById('constraintMetadataGraph')),doc=mxUtils.parseXml(xml);
 const input=[...doc.getElementsByTagName('mxCell')].find(c=>c.getAttribute('id')==='0');
 const expected=input?.getAttribute(key);if(!expected)throw Error('missing_native_root_constraint_property');
 new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],graph.model);graph.view.validate();
 const encoded=()=>new mxCodec().encode(graph.model);
 const metadata=()=>[...encoded().getElementsByTagName('mxCell')].find(c=>c.getAttribute('id')==='0')?.getAttribute(key);
 const before=metadata(),originalModel=mxUtils.getXml(encoded());
 const vertex=Object.values(graph.model.cells).find(c=>c.vertex&&c.geometry&&!c.geometry.relative);
 if(!vertex)throw Error('missing_editable_native_vertex');
 const original=vertex.geometry.clone(),moved=original.clone();moved.x+=17;moved.y+=11;
 graph.model.setGeometry(vertex,moved);graph.view.validate();const during=metadata();
 graph.model.setGeometry(vertex,original);graph.view.validate();const after=metadata();
 const result={input_present:true,after_actual_decode_exact:before===expected,after_actual_move_exact:during===expected,
  after_restore_exact:after===expected,logical_model_restore_exact:mxUtils.getXml(encoded())===originalModel,
  source_constraints_count:JSON.parse(expected).length,edited_native_vertex:vertex.id,
  root_property_preserved_in_actual_target_codec:true};graph.destroy();return result;
}'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    from portable_native_fonts import ready_page
    from compiler_graphviz_visibility_scene_v1 import LAYOUT_ATTRIBUTE
    from playwright.sync_api import sync_playwright
    blob=args.record.read_bytes();record=json.loads(blob);code=(R/record['code_file']).read_bytes()
    if hashlib.sha256(code).hexdigest()!=record['code_sha256']:raise ValueError('candidate_code_changed')
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
        try:page=ready_page(browser);result=page.evaluate(SCRIPT,[code.decode(),LAYOUT_ATTRIBUTE])
        finally:browser.close()
    result.update(id=record['id'],record_file=dict(file=str(args.record),sha256=hashlib.sha256(blob).hexdigest()),
                  code_sha256=record['code_sha256'],producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),model_calls=0)
    result['ok']=all(result[k] is True for k in ('after_actual_decode_exact','after_actual_move_exact','after_restore_exact','logical_model_restore_exact'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
