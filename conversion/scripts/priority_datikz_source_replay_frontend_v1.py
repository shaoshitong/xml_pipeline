"""Current-runtime DaTikZ replay view; frozen source compiler functions stay unchanged."""
from pathlib import Path
import hashlib,json
import compiler_tikz_source_viewport_v1 as original
R=original.R;W=original.W
def configuration(data_root=R):
 out=original.configuration(data_root);pins=dict(out['pins'])
 for name in ['priority_datikz_source_replay_frontend_v1.py','priority_datikz_source_replay_quality_v1.py']:
  p=W/'scripts'/name;pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 return {**out,'policy':'priority_DaTikZ_current_runtime_source_replay_v1:'+hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()[:20],'pins':pins,'provider_original_PNG_fidelity_asserted':False,'source_replay_current_pinned_TeXLive2025_Poppler100dpi':True}
def check_source(record,xml,source,data_root,native_info=None):
 result=original.check_source(record,xml,source,data_root,native_info)
 if result.get('ok'):
  assert record['profile']=='tikz_current_runtime_source_replay_aligned' and record['raw_source_pair_id']!=record['id']
  result['evidence']['reference_contract']='fresh exact-source TeXLive2025 / Poppler100dpi PNG; original provider PNG is auxiliary, historical DPI not asserted'
 return result
def audit_editing(record,xml,source_profile,data_root):return original.audit_editing(record,xml,source_profile,data_root)
def registration_record(record,reference,xml,data_root):return original.registration_record(record,reference,xml,data_root)
