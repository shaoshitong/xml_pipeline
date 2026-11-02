"""Read-only original-source eligibility taxonomy. No rendering or conversion."""
import sys,json,sqlite3,collections,re,uuid,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_languages_source_layout_v1 as base
import compiler_native_languages_v1 as parser
sha=lambda b:hashlib.sha256(b).hexdigest()
owner=R/'release/compiler_iterations/plantuml_grammar_source_audit_v1'/uuid.uuid4().hex;owner.mkdir(parents=True)
patterns={
 'skinparam':r'^\s*skinparam\b','hierarchy_or_group':r'^\s*(?:package|namespace|frame|folder|rectangle|node|cloud|database|component)\b[^\n]*\{',
 'activity_action':r'^\s*:[^\n]+;\s*$', 'activity_control':r'^\s*(?:start|stop|if\s*\(|else\b|elseif\b|endif\b|fork\b|end\s+fork|repeat\b|while\s*\(|switch\s*\(|case\s*\(|endswitch\b|partition\b)',
 'class_model':r'^\s*(?:abstract\s+class|class|enum|annotation|entity)\b','state_model':r'^\s*state\b|\[\*\]',
 'sequence_participants':r'^\s*(?:participant|actor|boundary|control|collections)\b','sequence_controls':r'^\s*(?:activate|deactivate|autonumber|alt\b|opt\b|par\b|loop\b|return\b|destroy\b|create\b)',
 'usecase':r'^\s*usecase\b|^\s*\([^\n]+\)\s*(?:as\s+\w+)?\s*$',
 'notes':r'^\s*note\b','legend_or_title':r'^\s*(?:legend|title|header|footer|caption)\b','macro_or_include':r'^\s*!(?:include|define|definelong|function|procedure|theme|pragma|if|endif|unquoted|global|local|return)\b',
 'component_entities':r'^\s*(?:component|rectangle|node|database|cloud|queue|interface)\b|^\s*\[[^\n]+\]',
 'link_color_or_style':r'[-.]+\[[^\]\n]+\][-.]*[<>]?|[-.]+(?:left|right|up|down)[-.]+',
 'quoted_endpoints':r'^\s*"[^"\n]+"\s*[-.<|*o]+|[-.<>|*o]+\s*"[^"\n]+"',
 'non_uml_wrapper':r'^\s*@start(?!uml\b)[a-z]+', 'mindmap_or_wbs':r'^\s*\*{1,}\s+|^\s*[+\-]{2,}\s+',
}
counts=collections.Counter();reasons=collections.Counter();features=collections.Counter();unsupported_features=collections.Counter();first_tokens=collections.Counter();exclusive=collections.Counter();rows=[]
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
 columns=[x[1] for x in db.execute('pragma table_info(jobs)')];jobs=[dict(zip(columns,r)) for r in db.execute("select * from jobs where format='plantuml'")]
 for j in jobs:
  out=base.static_support(j);src=json.loads(j['input_record']);manifest=json.loads(j['input_manifest']);blob=(R/manifest['source_code']).read_bytes();assert sha(blob)==src['code_sha256'];text=blob.decode('utf-8-sig');flags=[name for name,pat in patterns.items() if re.search(pat,text,re.M|re.I)];supported=out['supported'];counts['total']+=1;counts['supported' if supported else 'unsupported']+=1;features.update(flags)
  r={'id':j['id'],'authoritative_format':j['format'],'source_sha256':src['code_sha256'],'supported':supported,'base_reason':out.get('reasons'),'source_feature_flags':flags}
  if not supported:
   reason=(out.get('reasons') or ['unknown'])[0]
   if reason.startswith('unrecognized statement: '):
    line=reason[len('unrecognized statement: '):];token=(re.match(r'[^\s({:]+',line) or ['empty'])[0];token=token.lower();category='unrecognized_statement';first_tokens[token if re.fullmatch(r'[!@a-z_]+',token) else 'identifier_or_symbol']+=1
   else:category=reason
   reasons[category]+=1;unsupported_features.update(flags)
   priority=['non_uml_wrapper','activity_action','class_model','state_model','sequence_participants','usecase','hierarchy_or_group','component_entities','mindmap_or_wbs']
   exclusive[next((name for name in priority if name in flags),'other_or_implicit')]+=1
  rows.append(r)
summary={'schema':'plantuml_original_source_grammar_audit_v1','owner':str(owner),'scope':dict(counts),'base_reason_categories':dict(reasons),'first_unrecognized_tokens':dict(first_tokens.most_common()),'all_source_feature_counts_overlapping':dict(features),'unsupported_feature_counts_overlapping':dict(unsupported_features),'unsupported_priority_feature_partition_inference':dict(exclusive),'classification_warning':'Feature regexes and priority partition describe source syntax only; they are not official engine diagram types. First parser failure may mask later unsupported constructs.','base_module':str(Path(base.__file__)),'base_sha256':sha(Path(base.__file__).read_bytes()),'parser_module':str(Path(parser.__file__)),'parser_sha256':sha(Path(parser.__file__).read_bytes()),'source_rendering':False,'conversions':0,'models':0,'canonical_mutations':0,'source_bytes_exported_locally':False}
(owner/'source_audit.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));summary['rows_sha256']=sha((owner/'source_audit.jsonl').read_bytes());(owner/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False))
