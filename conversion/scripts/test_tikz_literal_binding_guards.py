import copy,json
from native_worker import R,W,now
from tikz_literal_connectivity import bind
work=W/'tikz_literal_binding_pilot/005ba1ad9f186a039a10a06e5f3a3737c28f5ac490463601cf482ccbdfdc1cea/9153f0bafe33885ed228beacdef972bfb120ceb955261a2afcb5bcfd6260eaa9';dom=json.loads((work/'source_dom.json').read_text());r=json.loads((work/'baseline_record.json').read_text());xml=(work/'baseline.drawio').read_text();code=(R/r['original_source_code']).read_text();new,ok=bind(xml,dom,code);assert ok['complete'] and new==(work/'candidate.drawio').read_text();negative=[]
for name in ('missing_background','changed_shape','changed_text','unsafe_label_background'):
 bad=copy.deepcopy(dom)
 if name=='missing_background':bad['objects']=[o for o in bad['objects'] if o['id']!='v96']
 if name=='changed_shape':next(o for o in bad['objects'] if o['id']=='v96')['matrix'][4]+=5
 if name=='changed_text':next(o for o in bad['objects'] if o['id']=='v97t0')['text']='Wrong'
 if name=='unsafe_label_background':
  for o in bad['objects']:
   if o['id'] in ('v97t0','v98t0','v99t0','v100t0'):o['bbox']['y']-=2;o['bbox']['h']+=4
 result,proof=bind(xml,bad,code);assert result==xml and not proof['complete'],name;negative.append({'case':name,'issues':proof['issues']})
out={'at':now(),'ok':True,'accepted_case_output_unchanged':True,'failed_bindings_retain_exact_original_xml':negative};(W/'tikz_literal_binding_guard_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
