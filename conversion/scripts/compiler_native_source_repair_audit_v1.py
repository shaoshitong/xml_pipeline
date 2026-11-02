"""Full remaining native-source failure census; no rendering or conversion."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda value:hashlib.sha256(value).hexdigest()
raw=lambda value:(json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n').encode()


def readrows(path):return [json.loads(x)for x in Path(path).read_bytes().splitlines()if x]

def run(output):
    import compiler_iteration_inventory_v1 as inventory
    from native_worker import normalize
    from native_source_font_profile_v4 import _cells,style_values
    output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_native_source_repair_v1').resolve()):raise ValueError('native_failure_audit_outside_owner')
    output.mkdir(parents=True,exist_ok=False)
    scope,scope_info=inventory.read_scope(R);scope={i:x for i,x in scope.items()if x['format']=='drawio'}
    pointer=json.loads((R/'release/compiler_iterations/current.json').read_bytes());summary=R/pointer['inventory']
    if sha(summary.read_bytes())!=pointer['inventory_sha256']:raise ValueError('fully_audited_inventory_pointer_changed')
    info=json.loads(summary.read_bytes());qualified_path=summary.parent/'qualified.jsonl'
    if sha(qualified_path.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_inventory_changed')
    accepted={x['id']:x for x in readrows(qualified_path)if x['id']in scope};events=collections.defaultdict(list);mass_counts=collections.Counter()
    for ledger in sorted((R/'release/compiler_iterations/runs').glob('*/status.sqlite')):
        with sqlite3.connect('file:'+str(ledger)+'?mode=ro',uri=True,timeout=30)as database:
            for identifier,status,finished,request_json,result_json in database.execute('select id,status,finished_at,source,result from samples where status in ("qualified","abandoned")'):
                if identifier not in scope:continue
                request=json.loads(request_json);result=json.loads(result_json)
                if request.get('evaluation_phase')=='baseline':continue
                events[identifier].append(dict(ledger=str(ledger),status=status,finished=finished or'',request=request,result=result,result_sha256=sha(result_json.encode())))
                if status=='qualified'and result.get('manifest'):accepted[identifier]=result['manifest']
                if ledger.parent.name=='native_complete_export_20261101_round4_mass':mass_counts[status]+=1
    hashes={}
    for identifier,manifest in accepted.items():inventory.check_manifest(R,identifier,scope[identifier],manifest,hashes)
    reasons=collections.Counter();source_errors=collections.Counter();frontend_errors=collections.Counter();stage_counts=collections.Counter();feature_counts=collections.Counter();details=[]
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        for identifier in sorted(scope):
            job=database.execute('select*from jobs where id=?',(identifier,)).fetchone();source=json.loads(job[4]);manifest=json.loads(job[11])if job[11]else{}
            row=dict(id=identifier,qualified=identifier in accepted,source=source,events=len(events[identifier]),features={})
            try:
                code=(R/manifest['source_code']).resolve(strict=True).read_bytes()
                if sha(code)!=source['code_sha256']:raise ValueError('source_XML_hash_changed')
                xml,pages,_=normalize(code.decode());root=ET.fromstring(xml);cells=_cells(root);model=next(root.iter('mxGraphModel'))
                values=[cell.get('value','')for cell in cells.values()];styles=[style_values(cell)for cell in cells.values()]
                fonts=collections.Counter(style.get('fontFamily','<inherited>')for style in styles if style.get('fontFamily'))
                features=dict(pages=pages,cells=len(cells),vertices=sum(c.get('vertex')=='1'for c in cells.values()),edges=sum(c.get('edge')=='1'for c in cells.values()),rich_labels=sum('<'in v and'>'in v for v in values),inline_font_override_labels=sum(bool(re.search(r'(?:font-family|font-size|font-weight|font-style)\s*:|<font\b|<(?:b|i|strong|em)\b',v,re.I))for v in values),shadow_styles=sum(style.get('shadow')=='1'for style in styles),embedded_ext_fonts=bool(model.get('extFonts')),font_families=dict(fonts),declared_page=[model.get('pageWidth'),model.get('pageHeight')],original_normalized_code_sha256=sha(xml.encode()))
                row['features']=features
            except Exception as error:row['source_inventory_error']=str(error)
            if not row['qualified']:
                for name,value in row['features'].items():
                    if isinstance(value,bool)and value:feature_counts[name]+=1
                    elif isinstance(value,int)and value>0:feature_counts['has_'+name]+=1
                latest=max(events[identifier],key=lambda x:x['finished'])if events[identifier]else None
                if latest:
                    result=latest['result'];row['latest']=latest;reasons[result.get('reason','unknown')]+=1;stage_counts[result.get('phase','unknown')]+=1
                    evidence=R/result['evidence_directory']if result.get('evidence_directory')else None
                    if evidence and(evidence/'frontend_result.json').is_file():
                        path=evidence/'frontend_result.json';front=json.loads(path.read_bytes());row['frontend']=dict(file=str(path),sha256=sha(path.read_bytes()),result={k:v for k,v in front.items()if k!='record'})
                        message=str(front.get('error')or front.get('detail')or front.get('reason',''))
                        key=message.split(':',1)[0].split('\n')[-1];frontend_errors[key]+=1
                    if result.get('quality_report'):
                        path=R/result['quality_report'];quality=json.loads(path.read_bytes());row['quality']=dict(file=str(path),sha256=sha(path.read_bytes()),failures=quality.get('failures'),checks={name:value for name,value in quality.get('checks',{}).items()if name not in ('visual',)})
                        strings=[]
                        for item in quality.get('failures',[]):
                            value=item.get('reason','')if isinstance(item,dict)else str(item);strings.append(value)
                            match=re.search(r'native_export_original_source_proof_failed:(.*)',value)
                            if match:
                                try:
                                    errors=json.loads(match.group(1))
                                    for entry in errors:source_errors[entry.get('error')or entry.get('reason','unknown')]+=1
                                except Exception:source_errors[value]+=1
                            elif value!='underlying_full_native_quality_failed':source_errors[value.split(':',1)[0]]+=1
                else:reasons['no_terminal_current_compiler_event']+=1
            details.append(row)
    (output/'all_source_failures.jsonl').write_bytes(b''.join(raw(row)for row in details))
    result=dict(scope=len(scope),qualified=len(accepted),pending=len(scope)-len(accepted),old_mass=dict(mass_counts),latest_reasons=dict(reasons),latest_stages=dict(stage_counts),source_errors=dict(source_errors.most_common()),frontend_errors=dict(frontend_errors.most_common()),pending_source_features=dict(feature_counts),model_calls=0,conversions=0,renders=0,summary_scope=scope_info,inventory=str(summary),full_asset_hashes_verified=len(hashes),detail_file=str(output/'all_source_failures.jsonl'),detail_sha256=sha((output/'all_source_failures.jsonl').read_bytes()))
    (output/'summary.json').write_bytes(raw(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(json.dumps(run(args.output),ensure_ascii=False))
