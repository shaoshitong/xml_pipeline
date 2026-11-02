"""Finite Source API and consumed XML controls, with zero normal conversions."""
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET

import native_source_dynamic_label_guard_v1 as guard

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
OUTPUT=R/'release/compiler_iterations/controls/native_source_dynamic_label_guard_controls_20261101_v1/proof.json'
FEATURES=W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1/selected_source_feature_audit_v1.json'
FEATURE_SHA='43bf3a2c577dd858e6d55b41d98dcac1ee315666a81d05e21c34ff25317ba3e0'
IDS=('1dd0d806172a72c11520bd6b7772982774201d786b72d41b8b593cea38baeed3','253283bea8b4e46b48a5ed623aedb8efc3f0cb564a494759426a98e6c0cebdbc','442a7661ca7496fc399007216538ae5eddf4f1628450a6d0fb7e0aa57fd5c7b7','451de1956e703c741a0d4f0bd9344196d884a8a6cca691828f7605f11b5a511a','d8ac32bf44b021a52fd1cc6dcf3e5c0a99dbdb8cda500cf2f0cf6a74e6732679','e7c5f7d24541782eb321195399a2085a175001063b669bcb62edd58ba4e96fc5')


def xml(label,enabled=True,wrapper=True,tag='UserObject',style='namedHtmlStyle;',placeholder=None):
    model=ET.Element('mxGraphModel');root=ET.SubElement(model,'root');ET.SubElement(root,'mxCell',id='0');ET.SubElement(root,'mxCell',id='1',parent='0')
    if wrapper:
        attrs=dict(id='a',label=label,name='Bound source value',placeholders='1'if enabled else'0')
        if placeholder is not None:attrs['placeholder']=placeholder
        carrier=ET.SubElement(root,tag,attrs);ET.SubElement(carrier,'mxCell',parent='1',vertex='1',style=style)
    else:ET.SubElement(root,'mxCell',id='a',parent='1',vertex='1',value=label,style=style)
    return ET.tostring(model,encoding='unicode')


def run():
    import compiler_types_program_v1 as common
    import compiler_native_materialized_text_node_iteration_pool_v5 as pool
    import compiler_native_core2_qualified_variable_source_audit_v1 as audit
    from fixed_batch_conversion_adapters_v1 import CHROME
    from playwright.sync_api import sync_playwright
    from portable_native_fonts import ready_page
    import native_worker
    feature_blob=FEATURES.read_bytes()
    if common.sha(feature_blob)!=FEATURE_SHA:raise ValueError('consumed_source_features_changed')
    feature_ids={row['id']for row in json.loads(feature_blob)['rows']}
    if not set(IDS)<=feature_ids:raise ValueError('six_existing_source_controls_missing')
    cases=[]
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        db.execute('pragma query_only=ON');before=[db.execute('select*from jobs where id=?',(identifier,)).fetchone()for identifier in IDS]
    for job in before:
        result=guard.inspect_job(job,root=R)
        class NeverCallFrontend:
            def static_support(self,given):raise AssertionError('dynamic_source_reached_normal_frontend_support')
        routed=pool.static_support_from_job(NeverCallFrontend(),job)
        if result['supported']is not False or not result['findings']or routed['supported']is not False:raise ValueError('real_XML_object_expression_not_deferred:'+job[0])
        cases.append(dict(id=job[0],source_code_sha256=result['source_code_sha256'],finding_count=len(result['findings']),findings=result['findings'],pool_static_support_deferred=True,normal_calls=0))
    examples=[('XML_object_expression',xml('<b>%name%</b>'),True),('arbitrary_XML_object_tag',xml('<b>%name%</b>',tag='ArbitraryMetadata'),True),('named_style_without_html_flag',xml('%name%',style='someNamedStyle;'),True),('direct_property_placeholder',xml('literal',placeholder='name'),True),('string_value_style_flag',xml('<b>%name%</b>',wrapper=False,style='html=1;placeholders=1;'),False),('disabled_object',xml('<b>%name%</b>',enabled=False),False),('ordinary_percent',xml('100%'),False),('escaped_expression',xml('%%name%'),True),('reserved_expression_conservative',xml('%label%'),True)]
    semantic=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        try:
            page=ready_page(browser)
            api=page.evaluate('''()=>({pattern_source:Graph.prototype.placeholderPattern.source,pattern_flags:Graph.prototype.placeholderPattern.flags,isReplacePlaceholders:Graph.prototype.isReplacePlaceholders.toString(),convertValueToString:Graph.prototype.convertValueToString.toString(),getLabel:Graph.prototype.getLabel.toString(),replacePlaceholders:Graph.prototype.replacePlaceholders.toString()})''')
            for name,source,expected in examples:
                actual=page.evaluate('''xml=>{const g=new Graph(document.createElement('div'));try{const d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.documentElement,g.model);const c=g.model.getCell('a');return {label:g.getLabel(c),enabled:g.isReplacePlaceholders(c),object_value:typeof c.value==='object'};}finally{g.destroy();}}''',source)
                admission=guard.inspect_xml(source)
                if(admission['supported']is False)!=expected:raise ValueError('source_guard_API_control_disagrees:'+name)
                raw_label=next(row for row in guard.label_records(source)if row['cell']=='a')['labels'];raw_label=next(iter(raw_label.values()),'')
                if actual['label']!=raw_label and admission['supported']is not False:raise ValueError('expanded_native_label_was_admitted:'+name)
                semantic.append(dict(name=name,expected_deferred=expected,actual_deferred=admission['supported']is False,native_getLabel_changes_raw_label=actual['label']!=raw_label,native_enabled=actual['enabled'],source_XML_sha256=common.sha(source.encode()),raw_label_sha256=common.sha(raw_label.encode()),actual_label_sha256=common.sha(actual['label'].encode())))
        finally:browser.close()
    bundle=native_worker.native.renderer_path(R).parent/'assets/viewer-static.min.js'
    if common.sha(bundle.read_bytes())!=guard.RUNTIME_BUNDLE_SHA256:raise ValueError('guard_runtime_bundle_changed')
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:after=[db.execute('select*from jobs where id=?',(identifier,)).fetchone()for identifier in IDS]
    if before!=after:raise ValueError('dynamic_label_control_canonical_jobs_changed')
    audit_ref=audit.run();audit_proof=json.loads((R/audit_ref['file']).read_bytes())
    proof=dict(schema='native_source_dynamic_label_guard_controls_v1',producer=common.asset(Path(__file__)),source_guard=common.asset(Path(guard.__file__)),policy=guard.POLICY,runtime_bundle=common.asset(bundle),native_API=api,source_feature_evidence=common.asset(FEATURES),actual_source_cases=cases,all_six_native_object_expressions_deferred=True,synthetic_native_API_cases=semantic,actual_API_semantics_verified=True,qualified_source_audit=audit_ref,qualified_source_audit_complete=audit_proof['complete'],source_only=True,reference_pixels_read=False,quality_reports_read=False,new_heldout_quality_read=False,normal_source_conversion_calls=0,canonical_original_jobs_unchanged=True,model_calls=0,goal_complete=False)
    OUTPUT.parent.mkdir(parents=True,exist_ok=False);common.immutable(OUTPUT,common.raw(proof));return common.asset(OUTPUT)


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
