"""Quantify the real v1 marker change without publishing or waiving failures."""
import hashlib,json
from PIL import Image
from native_worker import R,W,now,native
from tikz_execution_marker_quality import check_marker_quality
sha=lambda b:hashlib.sha256(b).hexdigest()
report=json.loads((W/'tikz_execution_binding_pilot.json').read_text());assert report['ok'];folder=R/report['work'];record=json.loads((folder/'baseline_record.json').read_text());before=(folder/'baseline.drawio').read_text();after=(folder/'candidate.drawio').read_text();dom=json.loads((folder/'source_dom.json').read_text());width,height=Image.open(R/record['original_reference']).size
renderer=W/'rendering_paintbounds_strict/remote_render.py';cache=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
old=native.native_job(before,width,height,180,renderer,8192,cache);new=native.native_job(after,width,height,180,renderer,8192,cache);assert old['ok'] and new['ok'];assert new['png']==(folder/'candidate.png').read_bytes()
quality=check_marker_quality(old['png'],new['png'],after,dom,report['binding'],max_distance_px=1.)
out={'at':now(),'id':report['id'],'quality':quality,'source_code_sha256':record['source_code_sha256'],'baseline_xml_sha256':sha(before.encode()),'candidate_xml_sha256':sha(after.encode()),'before_native_png_sha256':sha(old['png']),'after_native_png_sha256':sha(new['png']),'marker_quality_module_sha256':sha((W/'scripts/tikz_execution_marker_quality.py').read_bytes()),'renderer_sha256':sha(renderer.read_bytes()),'published':False,'pilot_report':str((folder/'report.json').relative_to(R))};(W/'tikz_execution_marker_quality_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
