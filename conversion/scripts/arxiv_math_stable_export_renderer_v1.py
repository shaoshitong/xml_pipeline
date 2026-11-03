"""Stable per-export official GUID allocation; source XML and strict QA untouched."""
from pathlib import Path
import hashlib,json
from arxiv_math_uniform_viewport_renderer_v1 import MathSynced as Previous,POLICY as OLD_POLICY
POLICY=OLD_POLICY+'__deterministic_export_local_GUID_allocator_v1'
class MathSynced(Previous):
 def replay(self,xml,folder):
  prefix='source-replay-'+hashlib.sha256(xml.encode() if isinstance(xml,str) else xml).hexdigest()[:24]
  self.r.page.evaluate('''prefix=>{const g=__bulkUi.editor.graph;if(g.__stableGuidExport)throw Error('export wrapper already installed');const original=g.getSvg;g.getSvg=function(...args){const saved=Editor.guid;let ordinal=0;Editor.guid=()=>prefix+'-'+(ordinal++);try{return original.apply(this,args);}finally{Editor.guid=saved;}};g.__stableGuidExport=true;}''',prefix)
  proof=super().replay(xml,folder)
  proof.update(policy=POLICY,export_GUID_prefix=prefix,export_GUID_scope='synchronous getSvg only; original allocator restored in finally',official_WAR_and_source_XML_unchanged=True,existing_exact_restore_checks_unchanged=True)
  (Path(folder)/'synced_replay_proof.json').write_text(json.dumps(proof,indent=2)+'\n');return proof
