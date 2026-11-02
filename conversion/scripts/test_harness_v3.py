import copy,json,sqlite3
from native_worker import R,W,now
from harness_pool_v3 import passed,REQUIRED,semantic
from harness_context_v3 import build_context,compact_xml,hydrate,structure,sha
D=sqlite3.connect(W/'jobs.sqlite');results=[]
c={'structure':{'ok':True,'edges':6},'judge':dict(pass_=True),'source_coverage':{'status':'node_edge_text_match'},'fidelity_diagnostic':{'regression_guard_pass':True}}
c['judge']={'pass':True,'material_errors':[],'expected_semantic_connector_count':6,**{k:True for k in REQUIRED}};assert passed(c)
for key,value in [('fidelity_diagnostic',{'regression_guard_pass':False}),('source_coverage',{'status':'source_content_mismatch'}),('structure',{'ok':False,'edges':6})]:
 x=copy.deepcopy(c);x[key]=value;assert not passed(x);results.append({'negative_gate':key,'rejected':True})
for prefix in ['0186e98e','0001c7fc','007a96b7']:
 id,raw,inp,prev=D.execute('select id,input_record,input_manifest,output_record from jobs where id like ?',(prefix+'%',)).fetchone();source=json.loads(raw);out=json.loads(prev);work=W/'harness_v3_preflight'/id;work.mkdir(parents=True,exist_ok=True);ctx=build_context(source,json.loads(inp),out,work);xml=(R/out['code_file']).read_text();compact=compact_xml(xml,ctx);restored,used=hydrate(compact,ctx);s=structure(restored,ctx);assert s['ok'];assert len(ctx['required_asset_ids'])==4 if prefix=='0186e98e' else True;assert set(ctx['required_asset_ids'])<={a['asset_id'] for a in used};results.append({'id':id,'required_asset_ids':ctx['required_asset_ids'],'used':len(used),'source_data_available':bool(ctx['auxiliary']),'fonts':list(ctx['fonts']),'roundtrip_valid':s['ok']})
# Valid original group container is no longer a spurious sixth flowchart node.
id,raw,inp,prev=D.execute('select id,input_record,input_manifest,output_record from jobs where id like "004880%"').fetchone();out=json.loads(prev);archive=R/out['previous_candidate_archive'];ctx={'code':(R/json.loads(inp)['source_code']).read_text()};coverage=semantic(json.loads(raw),ctx,(archive/'diagram.drawio').read_text());assert coverage['status']=='node_edge_text_match',coverage;results.append({'id':id,'baseline_group_coverage':coverage})
report={'time':now(),'ok':True,'results':results};(W/'harness_v3_preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
