"""Already-seen source evidence only; no normal/front-end conversion claim."""
import json,sqlite3,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import html_source_flex_paragraph_frontend_v3 as F
from html_source_flex_paragraph_capture_v3 import capture_source
from html_source_paragraph_render_v9 import run as full_native
from html_source_paragraph_ink_v9 import ink_metrics
from html_paragraph_source_contract_v9 import original
key=uuid.uuid4().hex;root=W/'html_source_flex_paragraph_frontend_v3/computed_sizing_mechanisms'/key;cases=[]
for ident in ['50a8c0d1677fe48820a5dfaad4ce86ad0f4e43fce7a83cfb13257103b7f7f408','dafff24e94cc6558395edd515d425d825bc5fc0226171a6b8475248ac9029386']:
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(ident,)).fetchone()
 seed,_=original(None,job);work=root/ident;dom,ir,served,source_png,hidden,capture=capture_source(seed,work/'source');ir['viewport']=capture['viewport'];size=[v+64 for v in capture['viewport']];xml,_=F.lower(dom,ir,served,seed);initial=F.render_geometry(xml,size,work,'seed');xml,registration=F.register_source_boxes(xml,ir,initial['native_render'],dom);actual=full_native(xml,size,work/'registered');glyphs=F.source_glyph_checks(ir,actual['native_render']);bg=E.fromstring(xml)
 for c in bg.iter('mxCell'):
  if c.get('id','').startswith('source_paragraph_owner_'):c.set('value','')
 background=full_native(E.tostring(bg,encoding='unicode'),size,work/'background');ink=ink_metrics(source_png,hidden,actual['png'],background['png'],(32,32));assert ink['exact_same_domain_source_native_ink'],ink
 case={'id':ident,'actual_groups':len(ir['groups']),'maximum_grapheme_Range_error':max(g['maximum_grapheme_Range_error']for g in glyphs),'all_original_glyph_fonts_and_ranges_bound':True,'source_native_signed_ink_exact':True,'source_computed_auto_descendants':sum(e['layoutSizingCSS']['width']['literal']=='auto'for g in ir['groups']for e in g['cssEvidence'][1:]),'work':str(work),'normal_calls':0,'qualification_claimed':False};cases.append(case);print(json.dumps(case),flush=True)
p=R/'clean/html_flex_paragraph_rollout_v3/computed_sizing_mechanism'/(key+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'ok':True,'cases':cases,'normal_calls':0,'new_heldout':0},indent=2));print(json.dumps({'ok':True,'report':str(p)}))
