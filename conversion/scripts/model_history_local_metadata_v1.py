"""Export only projected existing local SDK usage/request metadata, never media."""
import json
from pathlib import Path
from model_history_ledger_v1 import Collector,IdentityResolver,scan_paths,reconcile
root=Path(__file__).resolve().parents[2]/'deepseek_cases'
# __file__ is work/drawio_conversion/...; the history lives in work/deepseek_cases.
root=Path(__file__).resolve().parent.parent/'deepseek_cases'
collector=Collector();scan_paths(collector,[root],IdentityResolver(root),progress=False);data=collector.serialize();mirrors=[]
for path in root.glob('**/remote_manifest.json'):
 value=json.loads(path.read_bytes());mirrors.append({'local_manifest':str(path),'remote':value.get('remote'),'verified_remote_archives':value.get('verified_remote_archives')})
data['local_remote_mirror_manifests']=mirrors;out=Path(__file__).with_name('model_history_local_metadata_snapshot_v1.json');out.write_text(json.dumps(data,indent=2)+'\n');result=reconcile(collector);print(json.dumps({'metadata_snapshot':str(out),'bytes':out.stat().st_size,'local_artifacts':len(collector.artifacts),'projected_unique_events':len(collector.events),'responses':len(result['responses']),'requests':len(result['requests']),'mirror_manifests':len(mirrors),'read_problems':collector.problems,'credentials_or_media_exported':False}))
