import json
from native_worker import W,now
from tikz_literal_connectivity import source_text_match

def fragment(text,y):return {'text':text,'bbox':{'x':0,'y':y,'w':30,'h':12}}
t=[fragment('Mort-',0),fragment('gage',16)]
assert source_text_match(t,'Mortgage');assert source_text_match(t,'Mort-gage');assert not source_text_match([fragment('Mort-',0),fragment('gage',0)],'Mortgage');assert not source_text_match(t,'Montage');assert t[0]['text']=='Mort-' and t[1]['text']=='gage'
out={'at':now(),'ok':True,'measured_line_break_hyphen_matches_original_word':True,'literal_hyphen_stays_literal':True,'same_line_hyphen_not_deleted':True,'different_word_rejected':True,'all_rendered_text_fragments_unchanged':True};(W/'tikz_hyphen_matching_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
