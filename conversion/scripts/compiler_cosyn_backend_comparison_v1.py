"""Fixed whole-consumed-C100 Graphviz14/2.43 PNG replay diagnostic.

Both profiles run exactly once per original captured DOT; no target fitting,
source rewriting, unseen cohort, SVG/native conversion or qualification.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
RUN_ID='fixed_C100_graphviz14_vs243_20261101_v1'
ROOT=R/'release/compiler_cosyn_backend_comparison_v1'/RUN_ID
WORK=W/'compiler_cosyn_backend_comparison_v1'/RUN_ID
INPUT=R/'release/compiler_iterations/programs/python_cosyn_forward_unseen100_20261101_v1/C.jsonl'
sha=lambda data:hashlib.sha256(data).hexdigest()
raw=lambda value:(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()


def immutable(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as file:file.write(blob);file.flush();os.fsync(file.fileno())


def profile_definitions():
    current=W/'runtime/graphviz';private=W/'runtime/graphviz_deb'
    return [dict(name='existing_graphviz14_1_2',executable=str(current/'bin/dot'),ELF=str((current/'bin/dot').resolve()),roots=[str(current)],extra_env=dict(LD_LIBRARY_PATH=str(current/'lib'),GVBINDIR=str(current/'lib/graphviz')),declared_version='14.1.2'),
            dict(name='private_graphviz2_43_0',executable=str(W/'runtime/plantuml_dot243_v1/dot'),ELF=str((private/'usr/bin/dot').resolve()),roots=[str(private),str(W/'runtime/plantuml_dot243_v1')],extra_env=dict(LD_LIBRARY_PATH=str(private/'usr/lib/x86_64-linux-gnu'),GVBINDIR=str(private/'usr/lib/x86_64-linux-gnu/graphviz')),declared_version='2.43.0',provenance_limit='Only dot/ELF/runtime files reused. No PlantUML source proof is applied to CoSyn.')]


def image_exact(a,b,mode='RGBA'):
    from PIL import Image
    left=Image.open(io.BytesIO(a)).convert(mode);right=Image.open(io.BytesIO(b)).convert(mode)
    return left.size==right.size and left.tobytes()==right.tobytes()


def freeze_profiles():
    import compiler_python_cosyn_frontend_v1 as original
    import compiler_cosyn_image_postprocess_v1 as official
    import sandbox_runner
    pins={**original.configuration()['pins'],**official.configuration()['pins']}
    for path in (Path(__file__),Path(sandbox_runner.__file__),Path(sys.executable).resolve(),Path('/bin/sh').resolve(),Path('/usr/bin/env').resolve()):pins[str(path)]=sha(path.read_bytes())
    definitions=profile_definitions()
    for profile in definitions:
        files={Path(profile['executable']),Path(profile['ELF'])}
        for directory in profile['roots']:files.update(path for path in Path(directory).rglob('*')if path.is_file())
        # Pin real dynamically resolved shared libraries for both the ELF and
        # every bundled plugin, under the exact fixed profile environment.
        for path in tuple(files):
            try:header=path.open('rb').read(4)
            except OSError:continue
            if header!=b'\x7fELF':continue
            result=subprocess.run(['ldd',str(path)],capture_output=True,text=True,env={**os.environ,**profile['extra_env']},timeout=20)
            for target in re.findall(r'(?:=>\s*)?(/[^\s()]+)',result.stdout):
                if Path(target).is_file():files.add(Path(target))
        profile['pins']={str(path):sha(path.read_bytes())for path in sorted(files)}
        profile['canonical_paths']={name:str(Path(name).resolve())for name in profile['pins']}
        pins.update(profile['pins'])
        version=subprocess.run([profile['executable'],'-V'],capture_output=True,text=True,env={**os.environ,**profile['extra_env']},timeout=20)
        profile['actual_version_stdout']=version.stdout;profile['actual_version_stderr']=version.stderr
        if version.returncode or profile['declared_version']not in version.stderr:raise ValueError('fixed_runtime_version_identity_failed:'+profile['name'])
    return dict(schema='fixed_consumed_C100_two_source_PNG_backend_profiles_v1',profiles=definitions,pins=pins,official_postprocess=official.configuration(),target_parameters_selected=False,per_sample_backend_choice=False,workers=4,PNG_replays_per_profile_per_sample=1,source_only=True,per_label_checks=False,diagnostic_only=True,qualified=False,model_calls=0)


def check_pins(freeze):
    for path,digest in freeze['pins'].items():
        if sha(Path(path).read_bytes())!=digest:raise RuntimeError('infrastructure_fixed_comparison_pin_changed:'+path)
    for profile in freeze['profiles']:
        if any(str(Path(path).resolve())!=target for path,target in profile['canonical_paths'].items()):raise RuntimeError('infrastructure_fixed_comparison_runtime_alias_retargeted')


def source_seed(request):
    import compiler_python_cosyn_frontend_v1 as frontend
    from compiler_capture_snapshot_v1 import check_snapshot,read
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:job=database.execute('select*from jobs where id=?',(request['id'],)).fetchone()
    if job is None or json.loads(job[4])!=request['source']:raise RuntimeError('infrastructure_fixed_comparison_original_Python_identity_changed')
    seed,original=frontend.original(dict(compiler_source_capture_snapshot=request['source_capture_snapshot']),job)
    check_snapshot(seed,request['source_capture_snapshot'])
    code=read(seed['original_source_code'],True);reference=read(seed['original_reference'],True);dot=read(request['source_capture_snapshot']['source_dot'],True);cached=read(request['source_capture_snapshot']['returned_png'])
    if sha(code)!=request['source']['code_sha256']or sha(reference)!=request['source']['image_sha256']or sha(dot)!=request['source_capture_snapshot']['source_dot_sha256']or sha(cached)!=request['source_capture_snapshot']['returned_png_sha256']:raise RuntimeError('infrastructure_fixed_comparison_Python_DOT_capture_hash_changed')
    return seed,dot,cached,reference


def one_case(request,freeze):
    from PIL import Image
    from sandbox_runner import run
    from auto_quality_common import image_quality
    import compiler_cosyn_image_postprocess_v1 as official
    directory=WORK/(str(request['seq']).zfill(3)+'_'+request['id']);directory.mkdir(parents=True,exist_ok=False)
    row=dict(id=request['id'],seq=request['seq'],source_code_sha256=request['source']['code_sha256'],source_image_sha256=request['source']['image_sha256'],source_capture_snapshot=request['source_capture_snapshot'],profiles={},diagnostic_only=True,qualified=False,model_calls=0)
    try:
        seed,dot,cached,reference=source_seed(request);reference_size=Image.open(io.BytesIO(reference)).size;cached_size=Image.open(io.BytesIO(cached)).size
        row.update(original_Python_DOT_capture_SHA_bound=True,reference_canvas=list(reference_size),cached_capture_canvas=list(cached_size))
        for profile in freeze['profiles']:
            work=directory/profile['name'];work.mkdir(exist_ok=False);immutable(work/'input.dot',dot);started=time.monotonic();result=dict(profile=profile['name'],PNG_attempts=1,qualified=False,diagnostic_only=True)
            try:
                for path,digest in profile['pins'].items():
                    if sha(Path(path).read_bytes())!=digest:raise RuntimeError('infrastructure_fixed_runtime_pin_changed:'+path)
                process=run(work,[profile['executable'],'-v','-Tpng','-o','/work/source.png','/work/input.dot'],timeout=90,extra_ro=[(Path(folder),Path(folder))for folder in profile['roots']],extra_env=profile['extra_env'])
                immutable(work/'stdout.log',process.stdout.encode());immutable(work/'stderr.log',process.stderr.encode());result['returncode']=process.returncode
                if process.returncode:raise ValueError('source_DOT_PNG_replay_failed:'+process.stderr[-3000:])
                png=(work/'source.png').read_bytes();result.update(PNG_ok=True,source_PNG_sha256=sha(png),source_PNG_file=str(work/'source.png'),raw_canvas=list(Image.open(io.BytesIO(png)).size),raw_RGBA_exact_capture=image_exact(png,cached),raw_RGBA_exact_reference=image_exact(png,reference))
                processed=official.postprocess(png,seed);result['official_postprocess_ok']=processed['ok'];result['official_mapping']=processed['mapping']
                if not processed['ok']:result['official_filter_reason']=processed['reason']
                else:
                    immutable(work/'official.png',processed['png']);result.update(official_PNG_sha256=sha(processed['png']),official_PNG_file=str(work/'official.png'),official_evidence=processed['evidence'],canvas_matches_reference=processed['mapping']['output_canvas']==list(reference_size),official_RGB_exact_reference=image_exact(processed['png'],reference,'RGB'))
                    if result['canvas_matches_reference']:
                        metrics=image_quality(reference,processed['png'],{},None);result['global_foreground_tile_diagnostic']=metrics
                        result['passes_global_diagnostic_only']=metrics['ok'];result['per_label_checks_performed']=False
                    else:result['metric_unavailable_reason']='canvas_mismatch_no_padding_cropping_scaling_or_registration_to_reference'
            except Exception as error:result.update(error_type=type(error).__name__,reason=str(error)[:6000])
            result['seconds']=time.monotonic()-started;immutable(work/'result.json',raw(result));row['profiles'][profile['name']]=result
    except Exception as error:row.update(error_type=type(error).__name__,reason=str(error)[:6000])
    immutable(directory/'result.json',raw(row));return row


def summarize(rows,freeze):
    import statistics
    summary=dict(total=100,recorded=len(rows),complete_ID_coverage=len({row['id']for row in rows})==100,profiles={},source_only=True,diagnostic_only=True,per_label_checks=False,qualified=False,model_calls=0)
    for profile in freeze['profiles']:
        name=profile['name'];values=[row['profiles'].get(name,{})for row in rows];metrics=[value['global_foreground_tile_diagnostic']for value in values if'global_foreground_tile_diagnostic'in value]
        summary['profiles'][name]=dict(PNG_attempts=sum(value.get('PNG_attempts',0)for value in values),PNG_success=sum(value.get('PNG_ok')is True for value in values),raw_RGBA_exact_capture=sum(value.get('raw_RGBA_exact_capture')is True for value in values),raw_RGBA_exact_reference=sum(value.get('raw_RGBA_exact_reference')is True for value in values),official_postprocess_success=sum(value.get('official_postprocess_ok')is True for value in values),canvas_matches_reference=sum(value.get('canvas_matches_reference')is True for value in values),official_RGB_exact_reference=sum(value.get('official_RGB_exact_reference')is True for value in values),global_diagnostic_only_pass=sum(value.get('passes_global_diagnostic_only')is True for value in values),global_metric_denominator=len(metrics),global_metric_means={key:statistics.mean(value[key]for value in metrics)if metrics else None for key in ('ssim_1024','foreground_tile_p10_ssim','foreground_precision_2px','foreground_recall_2px')})
    a,b=[profile['name']for profile in freeze['profiles']];paired=[row for row in rows if'global_foreground_tile_diagnostic'in row['profiles'].get(a,{})and'global_foreground_tile_diagnostic'in row['profiles'].get(b,{})]
    summary['paired_same_canvas_diagnostic']=dict(samples=len(paired),private243_higher_ssim=sum(row['profiles'][b]['global_foreground_tile_diagnostic']['ssim_1024']>row['profiles'][a]['global_foreground_tile_diagnostic']['ssim_1024']for row in paired),graphviz14_higher_ssim=sum(row['profiles'][a]['global_foreground_tile_diagnostic']['ssim_1024']>row['profiles'][b]['global_foreground_tile_diagnostic']['ssim_1024']for row in paired))
    return summary


def execute(nonce):
    import compiler_types_program_v1 as common
    from initial_conversion_process_v1 import identity
    freeze=json.loads((ROOT/'profiles.json').read_bytes());check_pins(freeze);owner={**identity(os.getpid()),'nonce':nonce,'argv':sys.argv,'watch':False};common.atomic(ROOT/'owner.json',owner);common.wait_ack(ROOT/('ack_'+nonce+'.json'),owner,nonce)
    try:
        payload=(ROOT/'input.jsonl').read_bytes()
        if sha(payload)!=freeze['input_manifest_sha256']:raise RuntimeError('infrastructure_fixed_C100_input_changed')
        requests=[json.loads(line)for line in payload.splitlines()if line];rows=[]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'))as executor:
            futures={executor.submit(one_case,request,freeze):request['seq']for request in requests}
            for future in concurrent.futures.as_completed(futures):
                row=future.result();rows.append(row);print(json.dumps(dict(seq=row['seq'],id=row['id'],recorded=True,diagnostic_only=True)),flush=True)
        rows.sort(key=lambda row:row['seq']);check_pins(freeze);immutable(ROOT/'all100_results.jsonl',b''.join(raw(row)for row in rows));summary=summarize(rows,freeze);summary.update(input_manifest_sha256=freeze['input_manifest_sha256'],profiles_sha256=sha((ROOT/'profiles.json').read_bytes()),all100_results_sha256=sha((ROOT/'all100_results.jsonl').read_bytes()),fixed_profiles_for_every_sample=True,no_target_parameters=True,no_candidates_published=True);immutable(ROOT/'summary.json',raw(summary));return summary
    except BaseException as error:common.atomic(ROOT/'failure.json',dict(reason=str(error),error_type=type(error).__name__,traceback=traceback.format_exc(),diagnostic_only=True,qualified=False));raise


def launch():
    import compiler_types_program_v1 as common
    from initial_conversion_process_v1 import identity
    ROOT.mkdir(parents=True,exist_ok=False);WORK.mkdir(parents=True,exist_ok=False);payload=INPUT.read_bytes();requests=[json.loads(line)for line in payload.splitlines()if line]
    if len(requests)!=100 or len({row['id']for row in requests})!=100 or any(row['source']['format']!='python'or row['source']['source']!='allenai--CoSyn-400K'for row in requests):raise ValueError('fixed_comparison_requires_exact_consumed_C100')
    freeze=freeze_profiles();freeze.update(input_manifest=str(INPUT),input_manifest_sha256=sha(payload),input_samples=100);immutable(ROOT/'input.jsonl',payload);immutable(ROOT/'profiles.json',raw(freeze));check_pins(freeze)
    nonce=uuid.uuid4().hex;argv=[sys.executable,'-B',str(Path(__file__).resolve()),'execute','--nonce',nonce]
    with(ROOT/'program.log').open('xb')as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    birth=identity(child.pid);deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if child.poll()is not None:raise RuntimeError('fixed_source_comparison_exited_before_handshake')
        try:
            owner=json.loads((ROOT/'owner.json').read_bytes());current=identity(child.pid)
            if birth and current and owner['pid']==child.pid and owner['start_ticks']==birth['start_ticks']==current['start_ticks']and owner['nonce']==nonce:
                immutable(ROOT/('ack_'+nonce+'.json'),raw(owner));result=dict(pid=child.pid,start_ticks=birth['start_ticks'],argv=argv,output=str(ROOT),profiles_sha256=sha((ROOT/'profiles.json').read_bytes()),input_manifest_sha256=sha(payload),workers=4,finite=True,watch=False,source_only=True,diagnostic_only=True,qualified=False);immutable(ROOT/'launch.json',raw(result));return result
        except(OSError,KeyError,ValueError):pass
        time.sleep(.05)
    raise RuntimeError('fixed_source_comparison_handshake_timeout_no_restart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('launch','execute'));parser.add_argument('--nonce');args=parser.parse_args();print(json.dumps(launch()if args.action=='launch'else execute(args.nonce)),flush=True)
