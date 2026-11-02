"""Source-affinity dispatcher for recorded-Cairo Graphviz surface-contact SVG.

Only the audited Graphviz-role source grammar is supported in this first unit.
Other SVG grammars remain explicitly pending for their own next compiler pass.
"""
from pathlib import Path
import hashlib,json
import compiler_svg_source_viewport_graphviz_v1 as branch
R=branch.R;W=branch.W;UNIT=branch.UNIT;UNITS={'svg':UNIT};VERSION='compiler_svg_source_viewport_frontend_v1'
raw=branch.raw

def configuration(data_root=R):
 c=branch.configuration(data_root);pins=dict(c['pins']);p=Path(__file__).resolve();pins[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return {**c,'unit':UNIT,'units':UNITS,'pins':pins,'policy':VERSION+':'+hashlib.sha256(raw(pins)).hexdigest()[:20]}
def static_support(record_or_job):return branch.static_support(record_or_job)
def convert(record,job,work):return branch.convert(record,job,work)
def repair(record,job,work):return convert(record,job,work)
def check_source(record,xml,source,data_root,native_info=None):return branch.check_source(record,xml,source,data_root,native_info)
def quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):return branch.quality_visual(record,xml,native_info,png,reference,source_profile,data_root)
def audit_editing(record,xml,source_profile,data_root=R):return branch.audit_editing(record,xml,source_profile,data_root)
