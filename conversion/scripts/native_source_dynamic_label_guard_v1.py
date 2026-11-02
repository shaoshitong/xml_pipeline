"""Source-only admission guard for immutable native font core v2.

The core observes Graph.getLabel, which can expand XML object expressions.
Those templates remain pending for a source-preserving compiler. No target
pixels, quality outcomes, conversions or source-specific allowlists are used.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

R=Path('/backup/shaoshitong/img2code_20261029')
POLICY='native_v2_source_XML_object_dynamic_labels_pending_v1'
RUNTIME_BUNDLE_SHA256='0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'
# Exact Graph.prototype.placeholderPattern from the pinned 32.6.1 runtime.
PLACEHOLDER_PATTERN = r'''%(date\{[^{}\n\r\u2028\u2029]*\}|[^%{}"'=;]+)%'''
_PATTERN=re.compile(PLACEHOLDER_PATTERN)
JOB_COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')


def sha(value):return hashlib.sha256(value).hexdigest()
def raw(value):return(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def models(xml):
    """Decode every source page, including compressed draw.io diagram pages."""
    root=ET.fromstring(xml)
    if root.tag=='mxGraphModel':return [root]
    if root.tag!='mxfile':raise ValueError('unknown_native_XML_root')
    pages=list(root.findall('diagram'))
    if not pages:raise ValueError('native_XML_has_no_diagram_pages')
    result=[]
    for page in pages:
        children=list(page)
        if children:
            if len(children)!=1 or children[0].tag!='mxGraphModel':raise ValueError('unknown_native_diagram_children')
            model=children[0]
        else:
            text=(page.text or'').strip()
            if not text:raise ValueError('empty_native_diagram_page')
            if not text.startswith('<'):text=urllib.parse.unquote(zlib.decompress(base64.b64decode(text),-15).decode('utf-8'))
            model=ET.fromstring(text)
        if model.tag!='mxGraphModel':raise ValueError('unknown_native_page_model')
        result.append(model)
    return result


def label_records(xml):
    """Internal raw source labels for static admission and source-only audits."""
    result=[]
    for page_index,model in enumerate(models(xml)):
        graph_root=model.find('root')
        if graph_root is None:raise ValueError('native_model_has_no_root')
        parents={child:parent for parent in model.iter()for child in parent}
        for offset,cell in enumerate(model.iter('mxCell')):
            parent=parents.get(cell);carriers=[]
            while parent is not None and parent is not graph_root and parent is not model:
                carriers.append(parent);parent=parents.get(parent)
            # Nested nonstandard object envelopes are conservatively inspected
            # at every XML ancestor; no inner tag can hide an enabled object.
            if not carriers:carriers=[None]
            for depth,wrapper in enumerate(carriers,1):
                is_object=wrapper is not None;carrier=wrapper if is_object else cell
                identifier=cell.get('id')or carrier.get('id')or'cell_without_id_'+str(offset)
                labels={key:value for key,value in carrier.attrib.items()if key=='label'or key.startswith('label_')}if is_object else{'value':cell.get('value','')}
                result.append(dict(page=page_index,cell=identifier,wrapper_depth=depth if is_object else 0,object_value=is_object,wrapper_tag=carrier.tag if is_object else None,placeholders_enabled=is_object and carrier.get('placeholders')=='1',direct_placeholder_present=is_object and'placeholder'in carrier.attrib,direct_placeholder_key=carrier.get('placeholder')if is_object else None,labels=labels,cell_value=cell.get('value',''),style=cell.get('style',''),object_attributes=dict(carrier.attrib)if is_object else{}))
    return result


def inspect_xml(xml):
    result=dict(schema='native_source_dynamic_label_guard_v1',policy=POLICY,runtime_bundle_sha256=RUNTIME_BUNDLE_SHA256,source_only=True,normal_source_conversion_called=False,supported=True,reasons=[],cells=0,object_values=0,enabled_object_values=0,style_only_placeholder_flags=0,findings=[])
    try:
        records=label_records(xml)
        for row in records:
            result['cells']+=1;result['object_values']+=int(row['object_value']);result['enabled_object_values']+=int(row['placeholders_enabled'])
            tokens=[token for token in row['style'].split(';')if token]
            if not row['placeholders_enabled']and any(token=='placeholders=1'for token in tokens):result['style_only_placeholder_flags']+=1
            if not row['placeholders_enabled']:continue
            fields=dict(row['labels'])
            # Ambiguous object+mxCell.value representations are conservatively
            # pending as well; no wrapper tag, html flag or named style can
            # bypass the raw object-expression guard.
            if row['cell_value']:fields['wrapped_mxCell.value']=row['cell_value']
            matches=[dict(field=field,expression_sha256=sha(match.group().encode()),reserved_literal=match.group()in('%label%','%tooltip%'),escaped=match.start()>0 and text[match.start()-1]=='%')for field,text in fields.items()for match in _PATTERN.finditer(text)]
            if row['direct_placeholder_present']or matches:
                result['findings'].append(dict(page=row['page'],cell=row['cell'],wrapper_depth=row['wrapper_depth'],wrapper_tag=row['wrapper_tag'],reason='native_XML_object_placeholder_property_role_pending'if row['direct_placeholder_present']else'native_XML_object_percent_label_expression_pending',direct_placeholder_present=row['direct_placeholder_present'],direct_placeholder_key_sha256=sha((row['direct_placeholder_key']or'').encode())if row['direct_placeholder_present']else None,labels_sha256={field:sha(text.encode())for field,text in fields.items()},native_pattern_matches=matches,named_style_token_sha256=[sha(token.encode())for token in tokens if'='not in token],conservative_reserved_or_escape_deferral=any(m['reserved_literal']or m['escaped']for m in matches)))
        if result['findings']:
            result.update(supported=False,reasons=['deferred_native_source_dynamic_label_template_pending'],pending_for_source_preserving_core=True)
    except (ET.ParseError,ValueError,UnicodeError,zlib.error,TypeError)as error:
        result.update(supported=False,reasons=['deferred_native_source_XML_label_semantics_unknown_pending'],pending_for_source_preserving_core=True,parse_error_type=type(error).__name__,parse_error=str(error)[:500])
    return result


def inspect_job(job,root=R):
    """Read only the full canonical source payload; hashes bind the admission."""
    root=Path(root).resolve()
    if not isinstance(job,dict):
        if len(job)!=len(JOB_COLUMNS):raise RuntimeError('infrastructure_native_label_guard_requires_full13_canonical_columns')
        job=dict(zip(JOB_COLUMNS,job))
    source=json.loads(job['input_record'])
    if(source.get('pair_sha256'),source.get('category'),source.get('format'),source.get('source'))!=(job['id'],job['category'],job['format'],job['source']):raise RuntimeError('infrastructure_native_label_guard_canonical_source_identity_changed')
    if source['format']!='drawio':raise ValueError('native_label_guard_requires_drawio_source')
    manifest=json.loads(job['input_manifest'])
    path=(root/manifest['source_code']).resolve(strict=True)
    if not path.is_relative_to(root):raise RuntimeError('infrastructure_native_label_guard_original_payload_outside_root')
    payload=path.read_bytes()
    if sha(payload)!=source['code_sha256']:raise RuntimeError('infrastructure_native_label_guard_original_payload_hash_changed')
    result=inspect_xml(payload.decode('utf-8-sig'))
    result.update(id=job['id'],source_code_sha256=source['code_sha256'],input_record_sha256=sha(job['input_record'].encode()),input_manifest_sha256=sha(job['input_manifest'].encode()),source_payload=str(path.relative_to(root)))
    return result
