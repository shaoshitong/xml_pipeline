#!/usr/bin/env python3
"""Offline metadata QC; reads canonical catalogs, never modifies datasets/state.
Writes only its report. Content decoding/hash QC is handled by audit_catalog_content.py.
"""
import argparse, collections, hashlib, json, sqlite3, time
from pathlib import Path

UNKNOWN=('not stated','not shown','not specified','not checked','unspecified','unknown','other/','missing')

def read_json(path, default=None):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return default

def normalize(value):return str(value or '').replace('/','--').lower()

def main(args):
    root=args.root.resolve();issues=collections.Counter();examples={};groups={};pair_sets={};image_sets={};source_counts=collections.Counter();records={};inventory={}
    def issue(key,detail):
        issues[key]+=1
        if len(examples.setdefault(key,[]))<args.examples:examples[key].append(detail)
    # Use downloaded research and fixed-commit inventories; do not request any URL.
    catalogs=[root/'scripts/dataset_sources.json',root/'source_research.json',root/'dataset_sources.json']
    if args.sources:catalogs.insert(0,args.sources)
    for path in catalogs:
        data=read_json(path,{})
        items=data.get('datasets',[]) if isinstance(data,dict) else []
        for record in items:
            if record.get('id'):records.setdefault(normalize(record['id']),record)
    runs=[]
    states=[root]+(sorted((root/'runs').glob('*')) if (root/'runs').is_dir() else [])
    for state in states:
        data=read_json(state/'download_inventory.json',[])
        if isinstance(data,list):
            for repo in data:
                rid=normalize(repo.get('repo_id'));inventory[rid]=repo
                record=repo.get('source_research')
                if isinstance(record,dict):records.setdefault(rid,record)
        manifest=read_json(state/'download_manifest.json',{})
        if manifest:
            summary=manifest.get('summary',manifest)
            files=manifest.get('files',[]);complete=sum(x.get('status') in ('complete','already_complete') for x in files)
            planned=sum(len(x.get('files',[])) for x in data) if isinstance(data,list) else None
            run={'name':'priority' if state==root else state.name,'planned_inventory_files':planned,'manifest_complete_files':complete,'manifest_files':len(files),'finished':manifest.get('finished',summary.get('finished')),'failed_files':sum(x.get('status')=='failed' for x in files)}
            runs.append(run)
            if planned is not None and complete<planned:issue('download_run_not_complete',run)
    for kind,folder in [('provided','clean'),('derived','derived')]:
        path=root/folder/'manifest.jsonl';stats={'rows':0,'formats':collections.Counter(),'sources':collections.Counter(),'categories':collections.Counter(),'image_provenance':collections.Counter(),'code_provenance':collections.Counter(),'render_versions':collections.Counter(),'code_render_checked':0};pairs=set();images=set()
        if not path.exists():issue('missing_canonical_manifest',str(path));groups[kind]=stats;pair_sets[kind]=pairs;image_sets[kind]=images;continue
        for line_number,line in enumerate(path.open(),1):
            try:row=json.loads(line)
            except ValueError:issue('invalid_json',{'path':str(path),'line':line_number});continue
            source=row.get('source_repo') or row.get('source','unknown');source_counts[normalize(source)]+=1;fmt=row.get('format') or row.get('code_format','unknown');provenance=row.get('gold_code_provenance') or row.get('code_provenance') or row.get('provenance') or 'missing';image_prov=row.get('image_provenance') or row.get('provenance') or 'missing'
            ref={'kind':kind,'line':line_number,'source':source,'format':fmt,'code_provenance':provenance,'image_provenance':image_prov}
            stats['rows']+=1
            for key,value in [('formats',fmt),('sources',source),('categories',row.get('category','unknown')),('image_provenance',image_prov),('code_provenance',provenance),('render_versions',row.get('render_version') or 'legacy_or_not_applicable')]:stats[key][value]+=1
            stats['code_render_checked']+=bool(row.get('code_execution_checked'))
            if provenance=='missing':issue('missing_code_provenance',ref)
            if image_prov=='missing':issue('missing_image_provenance',ref)
            source_norm=normalize(source)
            if 'dwt_drawio' in source_norm:
                if provenance!='reconstructed_codex_subagent':issue('dwt_provenance_not_explicit_community_reconstruction',ref)
                if row.get('original_author_gold') is True:issue('dwt_falsely_original_author_gold',ref)
            if 'presto-design--svg_basic' in source_norm:issue('generic_svg_presto_in_target_catalog',ref)
            if 'ahazimeh--slide2svg' in source_norm:issue('raster_wrapper_slide2svg_in_editable_catalog',ref)
            if 'arxiv' in source_norm and ('pilot' in source_norm or 'source' in source_norm):issue('unverified_arxiv_pilot_in_canonical_catalog',ref)
            if kind=='derived' and fmt in ('drawio','xml','mxgraph','mxGraph XML/drawio'):
                if image_prov!='rendered_from_selected_native_drawio' or row.get('pairing')!='derived_from_native_drawio':issue('derived_native_code_not_rendered_from_selected_native',ref)
                if provenance in ('embedded_original_drawio','original_author_gold'):issue('embedded_exporter_authorship_overclaim',ref)
                if not row.get('code_execution_checked'):issue('derived_native_render_not_checked',ref)
            if row.get('code_execution_checked') and kind=='derived' and not row.get('render_validation_scope'):issue('render_check_scope_unspecified',ref)
            image_sha=row.get('image_sha256');code_sha=row.get('code_sha256')
            if image_sha and code_sha:
                digest=hashlib.sha256((image_sha+code_sha).encode()).hexdigest()
                if digest in pairs:issue('duplicate_pair_inside_canonical_kind',ref)
                pairs.add(digest);images.add(image_sha)
            else:issue('missing_hashes',ref)
            for key in ('clean_file','reference_image','image_file','code_file'):
                if row.get(key):
                    locator=(root/row[key]).resolve()
                    try:locator.relative_to(root)
                    except ValueError:issue('locator_outside_collection_root',{**ref,'key':key})
        stats['unique_pairs']=len(pairs);stats['unique_images']=len(images);groups[kind]={k:dict(v) if isinstance(v,collections.Counter) else v for k,v in stats.items()};pair_sets[kind]=pairs;image_sets[kind]=images
    coverage=[]
    for source,count in sorted(source_counts.items()):
        research=records.get(source,{});inv=inventory.get(source,{});license_text=research.get('license');card_license=inv.get('license_hf_card');known=bool(license_text and not any(x in license_text.lower() for x in UNKNOWN)) or bool(card_license)
        row={'source':source,'canonical_rows':count,'research_license':license_text,'hf_card_license':card_license,'source_url':research.get('source') or research.get('primary_reference'),'fixed_revision':inv.get('revision'),'license_statement_available':known,'note':'A dataset/card license does not settle rights in every upstream image; retain original attribution and source-specific restrictions.'}
        coverage.append(row)
        if not research:issue('source_research_record_missing',{'source':source,'rows':count})
        if not known:issue('license_unknown_or_unverified',{'source':source,'rows':count,'research_license':license_text})
        if not inv.get('revision') and not source.startswith('jgraph--'):issue('hf_fixed_revision_not_found',{'source':source,'rows':count})
    pilot=[]
    for base in [root/'arxiv_pilot',root/'raw/arxiv-source-pilot',root/'raw/arxiv_source_pilot',root/'arxiv_source_pilot']:
        data=read_json(base/'manifest.json')
        if isinstance(data,dict):
            item={'path':str(base/'manifest.json'),'complete_pairs_claimed':data.get('complete_pairs_claimed'),'indexed_papers':data.get('indexed_papers')};pilot.append(item)
            if data.get('complete_pairs_claimed',0)!=0:issue('arxiv_static_pilot_overclaims_pairs',item)
    ledger={};db_path=root/'manifests/derived_state.sqlite'
    if db_path.exists():
        try:
            with sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True) as db:
                ledger=dict(db.execute('SELECT status,COUNT(*) FROM items GROUP BY status').fetchall())
        except sqlite3.Error as exc:issue('derived_ledger_unreadable',str(exc))
    report={'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'read_only_data_audit':True,'content_hashes_recomputed':False,'groups':groups,'cross_kind':{'exact_pair_overlap':len(pair_sets['provided']&pair_sets['derived']),'unique_pair_union':len(pair_sets['provided']|pair_sets['derived']),'exact_image_overlap':len(image_sets['provided']&image_sets['derived']),'unique_image_union':len(image_sets['provided']|image_sets['derived'])},'issues':dict(issues),'bounded_examples':examples,'source_license_provenance':coverage,'download_runs':runs,'arxiv_static_pilot':pilot,'derived_ledger':ledger,'notes':['Domain categories are automated labels, not proof of academic provenance. Generic scientific/software/business flows may remain.','Community reconstructions, aggregate/model-generated source, and rendered-derived images are distinct from original-author source/image gold.','This metadata audit complements, and does not replace, bounded content hash/decode checks and visual inspection.']}
    critical_keys=('missing_canonical_manifest','invalid_json','generic_svg_presto_in_target_catalog','raster_wrapper_slide2svg_in_editable_catalog','unverified_arxiv_pilot_in_canonical_catalog','derived_native_code_not_rendered_from_selected_native','embedded_exporter_authorship_overclaim','derived_native_render_not_checked','dwt_provenance_not_explicit_community_reconstruction','dwt_falsely_original_author_gold','duplicate_pair_inside_canonical_kind','missing_hashes','locator_outside_collection_root')
    report['critical_issues']={key:issues[key] for key in critical_keys if issues[key]}
    report['ok']=not report['critical_issues'];report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    output=args.output or root/'reports/provenance_qc.json';output.parent.mkdir(parents=True,exist_ok=True);temp=output.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2));temp.replace(output)
    print(json.dumps({'report':str(output),'groups':{k:v.get('rows',0) for k,v in groups.items()},'cross_kind':report['cross_kind'],'issues':dict(issues)},ensure_ascii=False),flush=True)
    return int(not report['ok'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--sources',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--examples',type=int,default=5);raise SystemExit(main(parser.parse_args()))
