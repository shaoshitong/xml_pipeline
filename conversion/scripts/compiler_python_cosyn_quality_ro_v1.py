"""Independent full native QA with the official forward SOURCE pixel frame."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import time

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='independent_CoSyn_official_frame_intrinsic_glyph_native_quality_v1'
sha=lambda value:hashlib.sha256(value).hexdigest()


OBJECT_EDIT_SCRIPT=r'''async ([xml,requests])=>{
 document.body.innerHTML='<div id="CoSynObjectEditGraph" style="width:8192px;height:8192px;position:relative"></div>';
 const doc=mxUtils.parseXml(xml),model=doc.getElementsByTagName('mxGraphModel')[0];
 let css='';for(const pair of (model.getAttribute('extFonts')||'').split('|')){if(!pair)continue;const i=pair.indexOf('^');if(i<1)throw Error('invalid_inline_font');css+='@font-face{font-family:'+JSON.stringify(pair.slice(0,i))+';src:url('+JSON.stringify(pair.slice(i+1))+');font-weight:normal;font-style:normal;}';}
 const style=document.createElement('style');style.textContent=css;document.head.appendChild(style);
 const g=new Graph(document.getElementById('CoSynObjectEditGraph'));new mxCodec(doc).decode(model,g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();
 const encoded=()=>new mxCodec().encode(g.model),serialized=()=>mxUtils.getXml(encoded());
 const metadata=element=>Object.fromEntries([...element.getElementsByTagName('mxCell')].find(c=>c.getAttribute('id')==='0').getAttributeNames().filter(k=>k.startsWith('data')).sort().map(k=>[k,[...element.getElementsByTagName('mxCell')].find(c=>c.getAttribute('id')==='0').getAttribute(k)]));
 const expectedMetadata=JSON.stringify(metadata(model)),actualMetadata=()=>JSON.stringify(metadata(encoded()));
 if(actualMetadata()!==expectedMetadata)throw Error('source_frame_or_layout_metadata_dropped_by_actual_codec');
 const paint=c=>{const s=g.view.getState(c);if(!s)throw Error('source_object_missing_actual_state');return JSON.stringify({x:s.x,y:s.y,w:s.width,h:s.height,points:s.absolutePoints?.map(p=>p&&[p.x,p.y]),shape:s.shape?.node?.outerHTML,text:s.text?.node?.outerHTML});};
 const rows=[];
 for(const request of requests){
  const c=g.model.getCell(request.native);if(!c)throw Error('source_object_has_no_native_cell');
  const before=serialized(),paintBefore=paint(c),geometry=c.geometry.clone(),originalStyle=c.style;
  if(request.side){const key=request.side+'Size',value=+(g.getCellStyle(c)[key]||0);g.model.setStyle(c,mxUtils.setStyle(c.style,key,String(value+3)));}
  else{
   const moved=geometry.clone();
   if(c.edge){moved.points=(geometry.points?.length?geometry.points:g.view.getState(c).absolutePoints.slice(1,-1)).map(p=>new mxPoint(p.x+17,p.y+11));if(!moved.points.length){const p=g.view.getState(c).absolutePoints;moved.points=[new mxPoint((p[0].x+p.at(-1).x)/2+17,(p[0].y+p.at(-1).y)/2+11)];}}
   else if(moved.relative){moved.offset=(moved.offset||new mxPoint()).clone();moved.offset.x+=17;moved.offset.y+=11;}
   else{moved.x+=17;moved.y+=11;}
   g.model.setGeometry(c,moved);
  }
  g.view.validate();const changed=paint(c)!==paintBefore,preserved=actualMetadata()===expectedMetadata;
  g.model.setGeometry(c,geometry);g.model.setStyle(c,originalStyle);g.view.validate();
  rows.push({source_object:request.source,native_object:c.id,marker_side:request.side||null,actual_upstream_paint_changed:changed,source_frame_and_layout_metadata_preserved:preserved,logical_model_restore_exact:serialized()===before});
 }
 const result={objects:rows,source_objects:requests.length,actual_codec_metadata_preserved:true,all_source_objects_independently_intervened:rows.length===requests.length&&rows.every(r=>r.actual_upstream_paint_changed&&r.source_frame_and_layout_metadata_preserved&&r.logical_model_restore_exact)};g.destroy();return result;
}'''


def object_editing(xml,dom,markers):
    from playwright.sync_api import sync_playwright
    from portable_native_fonts import ready_page
    from fixed_batch_conversion_adapters_v1 import CHROME
    arrows={x['source_arrow_object']:x for x in markers['native_graphviz_arrowheads']}
    requests=[]
    for obj in dom['objects']:
        arrow=arrows.get(obj['id'])
        requests.append(dict(source=obj['id'],native=arrow['native_edge'],side=arrow['side'])if arrow else dict(source=obj['id'],native=obj['id']))
    with sync_playwright()as playwright:
        browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        try:page=ready_page(browser);return page.evaluate(OBJECT_EDIT_SCRIPT,[xml,requests])
        finally:browser.close()


def require(condition,reason):
    if not condition:raise ValueError(reason)


def verify(identifier,record_file,data_root,plugin_file,work,database=W/'jobs.sqlite'):
    import compiler_python_cosyn_frontend_v1 as frontend
    import compiler_python_cosyn_frame_v1 as frame
    import compiler_graphviz_visibility_domain_v1 as domain
    import compiler_graphviz_visibility_text_v1 as text
    from compiler_graphviz_visibility_scene_v1 import _read,_json_endpoint_validation
    from auto_quality_common_v4 import structure_checks,resource_checks,require_rendered_text
    from auto_quality_common import image_quality
    from auto_quality_source_vector_v2 import _graphviz_coverage
    from strict_canvas_gate import require_declared_page
    started=time.monotonic();work=Path(work).resolve();record_file=Path(record_file).resolve(strict=True)
    require(Path(data_root).resolve()==R.resolve(),'CoSyn_wrong_data_root')
    require(work.is_relative_to((W/'prototype/candidate_quality_ro_v1').resolve())and not work.exists(),'CoSyn_unowned_QA_work')
    work.mkdir(parents=True,exist_ok=False);payload=record_file.read_bytes();record=json.loads(payload);config=frontend.configuration()
    report=dict(id=identifier,version=VERSION,input_record_sha256=sha(payload),implementation_pins=config['pins'],quality_policy=config['policy'],
                checks={},failures=[],ok=False,accepted=False,canonical_mutations=0,model_calls=0)
    try:
        require(Path(plugin_file).resolve()==Path(frontend.__file__).resolve(),'CoSyn_wrong_source_plugin')
        require(all(sha(Path(name).read_bytes())==digest for name,digest in config['pins'].items()),'infrastructure_CoSyn_implementation_pin_changed')
        with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=30)as original_database:
            job=original_database.execute('select*from jobs where id=?',(identifier,)).fetchone()
        require(job is not None and job[12]is None,'CoSyn_missing_or_owned_original_job')
        original=json.loads(job[4]);seed,canonical=frontend.original(record,job)
        queue=frontend.ordinary_queue_status(identifier);report['ordinary_queue_guard']=queue
        require(not queue['active'],'deferred_current_ordinary_Graphviz_v2_queue')
        require(canonical==job,'infrastructure_CoSyn_original_job_changed')
        require((record['id'],record['source_pair_sha256'],record['source_format'],record['source_code_sha256'],record['source_image_sha256'])==(identifier,identifier,'python',original['code_sha256'],original['image_sha256']),'CoSyn_candidate_original_identity_changed')
        xml=_read(record['code_file'],record['code_sha256']).decode();_read(record['image_file'],record['image_sha256'])
        _read(record['original_source_code'],record['source_code_sha256']);reference=_read(record['original_reference'],record['source_image_sha256'])
        report['checks']['structure']=structure_checks(xml)
        report['checks']['resources']=resource_checks(R,record,xml,reference)
        source=frame.source(seed,work/'independent_official_SOURCE')
        descriptor=record['compiler_python_cosyn_frame_v1']
        prior=json.loads(_read(descriptor['source_frame_proof']['file'],descriptor['source_frame_proof']['sha256']))
        registered=descriptor['registered_SOURCE_SVG']
        require(_read(registered['file'],registered['sha256'])==source['registered_svg'],'native_registered_SOURCE_SVG_not_fresh_official_frame')
        require(descriptor['mapping']==source['proof']['mapping']and prior['mapping']==source['proof']['mapping'],'native_official_forward_mapping_changed')
        require(prior['source_capture_snapshot']==seed['compiler_source_capture_snapshot'],'native_SOURCE_capture_proof_changed')
        dom,clips=frame.viewport_lowering(source['replay']['dom'],source['canvas'])
        carrier=dict(policy=frame.POLICY,source_code_sha256=seed['source_code_sha256'],source_image_sha256=seed['source_image_sha256'],
                     mapping=source['proof']['mapping'],original_source_svg_sha256=seed['source_render_svg_sha256'],
                     registered_source_svg_sha256=sha(source['registered_svg']),source_scene_sha256=sha(frame.raw(source['scene'])),source_viewport_clips=clips)
        require(descriptor['native_frame_carrier']==carrier,'native_frame_metadata_not_fresh_SOURCE_derived')
        positions=source['replay']['positions']
        markers=domain.marker_check(dom,xml);coverage=_graphviz_coverage(dom,xml,{'native_graphviz_arrowheads':markers['native_graphviz_arrowheads']})
        paint,shapes=frame.paint_and_shape(dom,xml,carrier,positions,source['replay']['faces'],source['registered_svg']);endpoints=_json_endpoint_validation(source['scene'],dom,xml)
        source_failures=markers['failures']+coverage['errors']+paint['errors']
        require(abs(paint['source_layout_translation']['dx'])<=domain.POSITION_TOLERANCE_PX and abs(paint['source_layout_translation']['dy'])<=domain.POSITION_TOLERANCE_PX,'native_SOURCE_frame_translation_changed')
        report['checks']['source']=dict(ok=not source_failures,evidence=dict(complete_source_coverage=not source_failures,
                  complete_original_SOURCE_and_official_frame_independently_reconstructed=True,source_frame_proof=source['proof_asset'],
                  source_nodes_edges=endpoints,source_markers=markers,source_coverage=coverage,source_paint=paint,source_intrinsic_glyph_shape=shapes))
        require(not source_failures,'CoSyn_complete_SOURCE_paint_or_semantics_failed:'+json.dumps(source_failures)[:5000])
        width,height=source['canvas'];png,info=text._render_observed(xml,width,height);require_declared_page(info,width,height)
        require(sha(png)==record['image_sha256'],'CoSyn_candidate_PNG_not_exact_actual_drawio_render')
        frame.save(work/'fresh.png',png)
        report['checks']['render']=dict(code_sha256=record['code_sha256'],image_sha256=sha(png),strict_outside_page_pixels=0,canvas=[width,height],actual_text_cells=len(info.get('actual_text_positions',[])),actual_upstream_drawio=True)
        report['checks']['text_paint']=require_rendered_text(xml,info)
        glyphs=domain.glyph_check(positions,info,[0,0]);fonts=domain.physical_font_check(record,xml,positions,source['replay']['faces'],info)
        usage=[font for row in info.get('actual_platform_font_usage',[])for font in row.get('fonts',[])if font.get('glyphCount',0)]
        embedded=bool(usage)and all(font.get('isCustomFont')for font in usage)
        report['checks']['fonts']=dict(all_rendered_fonts_embedded=embedded,actual_custom_font_glyphs=sum(font['glyphCount']for font in usage),physical_SOURCE_font_check=fonts)
        require(embedded and fonts['ok'],'CoSyn_actual_native_physical_SOURCE_font_failed:'+json.dumps(fonts['failures'])[:3000])
        require(glyphs['ok'],'CoSyn_fresh_intrinsic_SOURCE_grapheme_geometry_failed:'+json.dumps(glyphs['failures'])[:5000])
        expected=domain._positions(positions,[0,0]);same=image_quality(source['replay']['png'],png,{},expected)
        primitives=domain._primitive_positions(dom,[0,0]);primitive_pixels=image_quality(source['replay']['png'],png,{},primitives)
        require(primitive_pixels['text_regions_checked']==len(primitives),'incomplete_CoSyn_SOURCE_primitive_pixel_scope')
        cross=image_quality(reference,png,{},expected);retained=[failure for failure in cross['failures']if failure!=domain.CROSS_DOMAIN_DIAGNOSTIC_ONLY]
        checks=dict(source_original_reference_pixels=source['proof']['source_reference_visual'],fresh_source_graphemes=glyphs,
                    same_browser_source_native_pixels=same,source_primitive_pixels=primitive_pixels,
                    reference_nonlocal_pixels=dict(ok=not retained,failures=retained))
        report['checks']['compiler_source_domains']=dict(ok=all(row['ok']for row in checks.values()),checks=checks,
                   cross_reference_native_local_text_retained_as_existing_domain_diagnostic=True,original_thresholds_unchanged=same['thresholds'],
                   source_engine_original_reference_all_local_text_gates_required=True,native_SOURCE_browser_all_local_text_and_0_03px_glyph_gates_required=True)
        report['checks']['visual']={**cross,'ok':not retained,'failures':retained,'original_reference_visual':cross}
        require(all(row['ok']for row in checks.values()),'CoSyn_independent_source_domains_failed:'+json.dumps({key:value.get('failures',[])for key,value in checks.items()if not value['ok']})[:5000])
        from auto_quality_move import audit
        moves=audit(xml);expected_moves=2*report['checks']['structure']['edges']
        require(len(moves['moves'])==expected_moves,'incomplete_CoSyn_native_endpoint_interventions')
        for move in moves['moves']:
            require(abs(move['delta']['x']-17)<=.05 and abs(move['delta']['y']-11)<=.05,'CoSyn_native_endpoint_does_not_follow_node')
            require(all(abs(child['x']-17)<=.05 and abs(child['y']-11)<=.05 for child in move.get('child_deltas',[])),'CoSyn_source_node_label_does_not_follow_node')
            for group in move.get('label_member_deltas',[]):
                members=group['members'];require(all(abs(child['x']-members[0]['x'])<=.05 and abs(child['y']-members[0]['y'])<=.05 for child in members),'CoSyn_source_edge_label_background_and_text_split')
        individual=object_editing(xml,dom,markers)
        require(individual['all_source_objects_independently_intervened']and individual['source_objects']==len(dom['objects']),'CoSyn_not_every_SOURCE_object_is_independently_editable')
        frame.save(work/'endpoint_movement.json',frame.raw(moves));frame.save(work/'every_SOURCE_object_editing.json',frame.raw(individual))
        report['checks']['native_editing']=dict(ok=True,endpoint_moves=expected_moves,every_SOURCE_object_count=len(dom['objects']),
                   endpoint_proof=str((work/'endpoint_movement.json').relative_to(R)),every_object_proof=str((work/'every_SOURCE_object_editing.json').relative_to(R)),source_frame_and_layout_metadata_survive_actual_codec=True)
        require(all(sha(Path(name).read_bytes())==digest for name,digest in config['pins'].items()),'infrastructure_CoSyn_implementation_changed_during_QA')
        _read(record['code_file'],record['code_sha256']);_read(record['image_file'],record['image_sha256'])
        report.update(ok=True,accepted=True)
    except Exception as error:
        report['failures'].append(dict(type=type(error).__name__,reason=str(error)[:7000]))
        report['infrastructure_failure']=isinstance(error,(ImportError,ModuleNotFoundError))or str(error).startswith('infrastructure_')
    report['seconds']=time.monotonic()-started;frame.save(work/'report.json',frame.raw(report));return report
