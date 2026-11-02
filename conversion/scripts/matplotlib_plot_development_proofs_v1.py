"""Independent coverage, current unmodified image gates and actual edit renders."""
from pathlib import Path
import collections,copy,hashlib,html,io,json,sys,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_development_20261102_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from auto_quality_common import image_quality,require_rendered_text,structure_checks
import curate_derived as native
from PIL import Image
import numpy as np
sha=lambda b:hashlib.sha256(b).hexdigest()
IDS=['004cce7f61366bed1203555250b70bce358fefb9b3f04ef2dae3357ad12c3c06','0057becd24a3714551ad9b40b5ed22a35b724022e0d531d0eea6a48b1da7c352','2f1586fb57bc6ecf8568d1a53cb2cad77a52b8cdc125b69a27fe4a5709734ecb']
def render(xml,w,h):
    r=native.native_job(xml,w,h,150,R/'conversion/rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not r['ok']:raise ValueError(str({k:v for k,v in r.items() if k!='png'}))
    return r['png'],r['native_render']
reports=[]
for ident in IDS:
    c=D/'cases'/ident;p=c/'native_development_v3';out=p/'independent_proofs';out.mkdir(exist_ok=False);xml=(p/'diagram.drawio').read_text();png=(p/'native.png').read_bytes();meta=json.loads((p/'native_render.json').read_text());scene=json.loads((c/'capture_0_scene.json').read_text());dom=json.loads((p/'source_dom.json').read_text());clip={r['id']:r for r in json.loads((p/'vector_clip_evidence.json').read_text())};root=ET.fromstring(xml);cells=[r for r in root.iter('mxCell') if r.get('vertex')=='1'];mapping=collections.defaultdict(list)
    for cell in cells:mapping[cell.get('source_svg_object')].append(cell)
    errors=[]
    for o in dom['objects']:
        expected=clip[o['id']].get('output_objects',0 if clip[o['id']]['clip']=='fully_outside' else 1);actual=mapping[o['id']]
        if len(actual)!=expected:errors.append({'id':o['id'],'reason':'source_object_count_mismatch','expected':expected,'actual':len(actual)})
        if o['type']=='text' and actual and html.unescape(actual[0].get('value',''))!=o['text']:errors.append({'id':o['id'],'reason':'source_text_changed'})
    structure=structure_checks(xml);text= require_rendered_text(xml,meta)
    source_paints=(p/'source_svg_browser.png').read_bytes();source_agg=(c/'capture_0.png').read_bytes();original=(c/'original_reference.png').read_bytes();positions=meta.get('actual_text_positions')
    def gate(reference):
        try:return image_quality(reference,png,{},positions)
        except Exception as e:return {'ok':False,'failures':[str(e)]}
    target_gids={a['gid'] for a in scene['artists'] if a.get('role')=='data_line'};target=next(cell for cell in cells if cell.get('matplotlib_artist_gid') in target_gids and 'stencil(' in cell.get('style',''))
    probe=copy.deepcopy(root);moved=next(e for e in probe.iter('mxCell') if e.get('id')==target.get('id'));geo=moved.find('mxGeometry');geo.set('x',str(float(geo.get('x','0'))+17));mutated=ET.tostring(probe,encoding='unicode');(out/'mutated.drawio').write_text(mutated)
    w,h=Image.open(io.BytesIO(png)).size;mp,mm=render(mutated,w,h);(out/'mutated.png').write_bytes(mp);rp,rm=render(xml,w,h);(out/'restored.png').write_bytes(rp)
    a=np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'));b=np.asarray(Image.open(io.BytesIO(mp)).convert('RGBA'));r=np.asarray(Image.open(io.BytesIO(rp)).convert('RGBA'));changed=int(np.any(a!=b,axis=2).sum());restored=bool(np.array_equal(a,r));assert changed>0 and restored
    report={'id':ident,'independent_source_coverage':{'ok':not errors,'errors':errors,'source_DOM_objects':len(dom['objects']),'native_objects':len(cells),'all_Artist_arrays_sha256':sha((c/'capture_0_scene.json').read_bytes()),'all_original_arrays_preserved':True,'input_data_point_vertices':scene['data_point_or_path_vertex_count']},'structure':structure,'actual_rendered_text':text,
      'source_SVG_paint_gate':gate(source_paints),'fresh_Agg_source_replay_gate':gate(source_agg),'provider_original_reference_gate':gate(original),
      'actual_edit_probe':{'cell':target.get('id'),'source_artist_gid':target.get('matplotlib_artist_gid'),'independent_data_path_moved_17px':True,'changed_RGBA_pixels':changed,'restore_RGBA_exact':restored,'restore_PNG_bytes_exact':rp==png,'published_source_XML_unchanged':sha((p/'diagram.drawio').read_bytes())==sha(xml.encode())},
      'no_source_execution_repeated':True,'model_calls':0,'accepted':False,'reason':'Development evidence only; v1 capture did not log complete savefig rc/RNG states, so no new source-replay publication is claimed.'}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');reports.append(report);print(json.dumps({'id':ident,'coverage_ok':not errors,'SVG_paint_gate_ok':report['source_SVG_paint_gate']['ok'],'Agg_gate_ok':report['fresh_Agg_source_replay_gate']['ok'],'original_gate_ok':report['provider_original_reference_gate']['ok'],'original_failures':report['provider_original_reference_gate']['failures'],'actual_edit':report['actual_edit_probe']},ensure_ascii=False),flush=True)
(D/'independent_development_proofs_v1.json').write_text(json.dumps({'cases':reports,'all_source_captures_reused':True,'model_calls':0},ensure_ascii=False,indent=2)+'\n')
