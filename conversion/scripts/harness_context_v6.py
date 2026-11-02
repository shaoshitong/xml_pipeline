"""v5 source provenance plus independently verified fixed page dimensions."""
import json
import harness_context_v5 as core
from harness_context_v5 import prompt_assets,structure,sha,compact_xml,hydrate,verify_source_fullname_faces
from harness_canvas_contract import validate

def build_context(source,inp,previous,work):
    ctx=core.build_context(source,inp,previous,work)
    contract=validate(previous,ctx['reference']);ctx['native_canvas_contract']=contract
    ctx['reference_width'],ctx['reference_height']=ctx['width'],ctx['height']
    ctx['width'],ctx['height']=contract['output_page']
    audit=json.loads((work/'context.json').read_text());audit.update(width=ctx['width'],height=ctx['height'],reference_width=ctx['reference_width'],reference_height=ctx['reference_height'],native_canvas_contract=contract)
    (work/'context.json').write_text(json.dumps(audit,indent=2)+'\n');return ctx
