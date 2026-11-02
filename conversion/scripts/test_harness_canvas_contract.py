import copy,json,sqlite3,sys,uuid,xml.etree.ElementTree as E
from native_worker import R,W,native,now
from harness_canvas_contract import validate,require_xml_page,require_render,RENDERER
from harness_context_v6 import build_context,compact_xml,hydrate,structure,verify_source_fullname_faces
ID=sys.argv[1] if len(sys.argv)>1 else '03299a3c21789a81926f027324ec2c78cc9134ff3fc0e46e271f1699b3202c19'
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
raw,inp,previous,state=d.execute('select input_record,input_manifest,output_record,state from jobs where id=?',(ID,)).fetchone();source=json.loads(raw);prepared=json.loads(inp);record=json.loads(previous)
work=W/'harness_sessions'/('canvas_contract_preflight_'+uuid.uuid4().hex);work.mkdir()
ctx=build_context(source,prepared,record,work);contract=ctx['native_canvas_contract'];xml=(R/record['code_file']).read_text();png=(R/record['image_file']).read_bytes();require_xml_page(xml,contract)
compact=compact_xml(xml,ctx);restored,used=hydrate(compact,ctx);require_xml_page(restored,contract);assert structure(restored,ctx)['ok']
a=native.native_job(xml,ctx['width'],ctx['height'],150,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');b=native.native_job(restored,ctx['width'],ctx['height'],150,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
assert a['ok'] and b['ok'];require_render(a['native_render'],contract);require_render(b['native_render'],contract);assert a['png']==b['png']==png,'Fresh compact/hydrate actual pixels differ';verify_source_fullname_faces(ctx['verified_source_record'],b['native_render'])
(work/'fresh_native.png').write_bytes(b['png'])
next_record=copy.deepcopy(record);next_record.pop('native_page_padding',None);next_record['native_canvas_contract']=contract
assert validate(next_record,ctx['reference'])==contract
negative=[]
def rejects(label,fn):
 try:fn()
 except (AssertionError,KeyError,ValueError):negative.append(label)
 else:raise AssertionError('Negative guard accepted: '+label)
for key,value in [('output_page',[contract['output_page'][0]+1,contract['output_page'][1]]),('original_page_offset',[contract['original_page_offset'][0]+1,contract['original_page_offset'][1]]),('origin_record_sha256','0'*64),('origin_record','raw/untrusted/candidate_record.json')]:
 r=copy.deepcopy(next_record);r['native_canvas_contract'][key]=value;rejects(key,lambda:validate(r,ctx['reference']))
r=copy.deepcopy(record);r['source_code_sha256']='0'*64;rejects('source_identity',lambda:validate(r,ctx['reference']))
root=E.fromstring(restored);root.find('.//mxGraphModel').set('pageWidth',str(contract['output_page'][0]+1));rejects('model_page_resize',lambda:require_xml_page(E.tostring(root,encoding='unicode'),contract))
info=copy.deepcopy(b['native_render']);info['outside_page_pixel_audit']['nonwhite_outside_pixels']=1;rejects('one_offpage_pixel',lambda:require_render(info,contract))
info=copy.deepcopy(b['native_render']);info['renderer_module_sha256']='0'*64;rejects('renderer_change',lambda:require_render(info,contract))
# Confirm the legacy mismatch is the page-size gate, rather than weakening a fidelity gate.
from strict_canvas_gate import require_declared_page
rejects('legacy_reference_size_rejects_proven_page',lambda:require_declared_page(b['native_render'],*contract['reference_page']))
out={'at':now(),'ok':True,'id':ID,'state_at_start':state,'contract':contract,'negative_guards':negative,'fresh_stored_and_compact_hydrate_native_png_byte_identical':True,'inherited_contract_revalidated':True,'work':str(work.relative_to(R)),'accepted':False}
(W/('harness_canvas_contract_tests_'+ID+'.json' if len(sys.argv)>1 else 'harness_canvas_contract_tests.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
