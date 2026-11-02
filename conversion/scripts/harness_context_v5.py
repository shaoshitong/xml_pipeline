"""v4 native fonts plus immutable provenance across repeated model revisions."""
import copy,json
import harness_context_v4 as core
from harness_context_v4 import prompt_assets,structure,sha,compact_xml,hydrate,verify_source_fullname_faces
from harness_source_provenance import freeze,validate_frozen

def build_context(source,inp,previous,work):
 if previous and previous.get('source_provenance'):validate_frozen(previous['source_provenance'])
 proof=freeze(previous,work);effective=copy.deepcopy(previous)
 if proof:effective['source_font_recovery_archive']=proof['archive']
 ctx=core.build_context(source,inp,effective,work);ctx['source_provenance']=proof
 if proof:
  audit=json.loads((work/'context.json').read_text());audit['source_provenance']=proof;(work/'context.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
 return ctx
