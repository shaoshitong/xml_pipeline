"""Finite actual-render semantic controls for the official CoSyn frontend."""
import argparse
import copy
import json
from pathlib import Path
import re
import uuid
import xml.etree.ElementTree as ET


def run(positive_record,positive_report,output):
    import compiler_python_cosyn_intrinsic_frontend_v2 as frontend
    import compiler_python_cosyn_intrinsic_frame_v2 as frame
    import compiler_python_cosyn_intrinsic_quality_ro_v2 as quality
    import compiler_graphviz_visibility_text_v1 as text
    R,W=frame.R,frame.W;output=Path(output).resolve()
    if not output.is_relative_to((R/'release/compiler_python_cosyn_intrinsic_adapter_controls_v2').resolve()):raise ValueError('unowned_CoSyn_control_output')
    output.mkdir(parents=True,exist_ok=False)
    record=json.loads(Path(positive_record).read_bytes());report=json.loads(Path(positive_report).read_bytes());config=frontend.configuration()
    assert report['ok']and report['accepted']and report['id']==record['id']and report['implementation_pins']==config['pins']
    assert frame.sha(Path(positive_record).read_bytes())==report['input_record_sha256']
    assert all(frame.sha(Path(path).read_bytes())==digest for path,digest in config['pins'].items())
    xml=(R/record['code_file']).read_text();assert frame.sha(xml.encode())==record['code_sha256']
    original_png=(R/record['image_file']).read_bytes();assert frame.sha(original_png)==record['image_sha256']
    results=[]
    for kind in ('named_endpoint','SOURCE_text_matrix','SOURCE_intrinsic_viewport'):
        root=ET.fromstring(xml);cells=list(root.iter('mxCell'))
        if kind=='named_endpoint':
            edge=next(c for c in cells if c.get('edge')=='1'and c.get('source')!=c.get('target'))
            intervention=dict(cell=edge.get('id'),property='target',before=edge.get('target'),after=edge.get('source'));edge.set('target',edge.get('source'))
        elif kind=='SOURCE_text_matrix':
            cell=next(c for c in cells if 'data-cosyn-glyph-shape-v1' in c.get('value',''));value=cell.get('value');match=re.search(r'transform="matrix\(([^)]+)\)"',value)
            values=[float(v)for v in match.group(1).split(',')];values[4]+=1.;changed='matrix('+','.join(format(v,'.12g')for v in values)+')'
            intervention=dict(cell=cell.get('id'),property='SOURCE_text_CTM_e',before=match.group(0),after=changed)
            cell.set('value',value[:match.start()]+ 'transform="'+changed+'"'+value[match.end():])
        else:
            cell=next(c for c in cells if 'data-cosyn-glyph-shape-v1' in c.get('value',''));value=cell.get('value');match=re.search(r'(<svg\b[^>]*\bwidth=")([0-9]+)(")',value)
            before=match.group(2);after=str(int(before)+3)
            intervention=dict(cell=cell.get('id'),property='intrinsic_viewport_width_without_matching_viewBox',before=before,after=after);cell.set('value',value[:match.start(2)]+after+value[match.end(2):])
        changed=ET.tostring(root,encoding='unicode');assert changed!=xml
        width,height=record['render']['canvas'];png,info=text._render_observed(changed,width,height)
        assert frame.sha(png)!=record['image_sha256'],'negative_must_change_actual_native_pixels'
        destination=R/'clean/compiler_python_cosyn_intrinsic_controls_v2'/record['id'][:2]/record['id']/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False)
        frame.save(destination/'diagram.drawio',changed.encode());frame.save(destination/'image.png',png)
        negative={**record,'code_file':str((destination/'diagram.drawio').relative_to(R)),'code_sha256':frame.sha(changed.encode()),'image_file':str((destination/'image.png').relative_to(R)),'image_sha256':frame.sha(png),'render':info}
        path=output/(kind+'.candidate.json');frame.save(path,frame.raw(negative))
        work=W/'prototype/candidate_quality_ro_v1'/('cosyn_negative_'+kind+'_'+uuid.uuid4().hex)
        rejected=quality.verify(record['id'],path,R,frontend.__file__,work)
        assert not rejected['ok']and not rejected['accepted']and not rejected.get('infrastructure_failure'),'real_semantic_negative_must_be_rejected_without_infrastructure_failure'
        reasons=[row['reason']for row in rejected['failures']]
        if kind=='named_endpoint':assert any('endpoint'in reason or'coverage'in reason for reason in reasons)
        else:assert any('glyph_shape_matrix_changed'in reason for reason in reasons)
        results.append(dict(kind=kind,intervention=intervention,actual_native_pixels_changed=True,code_sha256=negative['code_sha256'],image_sha256=negative['image_sha256'],candidate_file=str(path),report=str(work/'report.json'),rejected=True,failures=rejected['failures']))
    controls=dict(ok=True,source_frontend_policy=config['policy'],source_frontend_pins=config['pins'],control_producer=dict(file=str(Path(__file__).resolve()),sha256=frame.sha(Path(__file__).read_bytes())),
                  positive=dict(id=record['id'],record_file=str(Path(positive_record).resolve()),record_sha256=frame.sha(Path(positive_record).read_bytes()),report_file=str(Path(positive_report).resolve()),report_sha256=frame.sha(Path(positive_report).read_bytes()),accepted=True,checks=report['checks']),
                  semantic_negatives=results,actual_codec_and_every_source_object_editing=report['checks']['native_editing'],ordinary_v2_queue_guard=record['ordinary_queue_guard'],
                  all_thresholds_unchanged=True,models=0,canonical_mutations=0)
    assert all(frame.sha(Path(path).read_bytes())==digest for path,digest in config['pins'].items())
    frame.save(output/'receipt.json',frame.raw(controls));frame.save(output/'qualified.jsonl',frame.raw(record));return controls


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--positive-record',required=True);parser.add_argument('--positive-report',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    receipt=run(args.positive_record,args.positive_report,args.output);print(json.dumps(dict(ok=receipt['ok'],positive=receipt['positive']['id'],negative_count=len(receipt['semantic_negatives']),receipt=str(Path(args.output)/'receipt.json'))))
