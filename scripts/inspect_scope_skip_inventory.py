#!/usr/bin/env python3
"""Read-only local-HKUST inventory of unconditional file-scope exclusions.
Only file listings, sizes and Parquet footers/schema are read; never row BLOBs.
"""
import argparse,collections,hashlib,importlib.util,json,time
from pathlib import Path


def main(args):
    import pyarrow.parquet as pq
    root=args.root.resolve();curator=args.curator or root/'scripts/curate_pairs_scope_draft.py';spec=importlib.util.spec_from_file_location('scope_inventory_draft',curator);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    began=time.monotonic();totals=collections.Counter();sources={};files=[];errors=[];complete=True
    eligible={'unknown','generic_svg_auxiliary','slide_aux','vinci','omni','cosyn'}
    for source in sorted((root/'raw').iterdir()):
        if not source.is_dir():continue
        profile=module.profile_for(source.name)
        if profile not in eligible:continue
        stats={'profile':profile,'fast_skippable_files':0,'fast_skippable_rows':0,'fast_skippable_raw_file_bytes':0,'paired_schema_guarded_files':0,'reasons':collections.Counter()}
        for file in sorted(source.rglob('*.parquet')):
            if time.monotonic()-began>args.seconds:complete=False;break
            totals['eligible_profile_parquet_files_seen']+=1;rel=file.relative_to(source);reason=module.file_scope_reason(profile,rel)
            if not reason:continue
            try:
                reader=pq.ParquetFile(file);rows=reader.metadata.num_rows;size=file.stat().st_size;paired={'tikz_code_i','tikz_code_j'}.issubset(reader.schema_arrow.names)
                if paired:
                    stats['paired_schema_guarded_files']+=1;totals['paired_schema_guarded_files']+=1;continue
                stats['fast_skippable_files']+=1;stats['fast_skippable_rows']+=rows;stats['fast_skippable_raw_file_bytes']+=size;stats['reasons'][reason]+=rows
                totals['fast_skippable_files']+=1;totals['fast_skippable_rows']+=rows;totals['fast_skippable_raw_file_bytes']+=size
                files.append({'source':source.name,'profile':profile,'raw_file':str(rel),'rows':rows,'raw_file_bytes':size,'reason':reason})
            except Exception as e:errors.append({'source':source.name,'raw_file':str(rel),'error':type(e).__name__+':'+str(e)[:150]})
        stats['reasons']=dict(stats['reasons']);sources[source.name]=stats
        if not complete:break
    result={'read_only':True,'complete_available_file_scan':complete,'observed_at_epoch':time.time(),'elapsed_seconds':round(time.monotonic()-began,3),'draft_path':str(curator),'draft_sha256':hashlib.sha256(curator.read_bytes()).hexdigest(),'totals':dict(totals),'sources':sources,'files':files,'footer_errors':errors,'interpretation':'Raw file byte sizes are the payload size whose materialization is avoidable, not measured physical disk reads. All rows still receive scope-rejection locators. Metadata-dependent domains are not skipped. Only currently present footer-readable files are counted.'}
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/backup/shaoshitong/img2code_20261029'));p.add_argument('--curator',type=Path);p.add_argument('--seconds',type=int,default=45);main(p.parse_args())
