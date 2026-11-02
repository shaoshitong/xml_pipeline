#!/usr/bin/env python3
"""Build auditable, deduplicated provided/derived pair catalogs on HKUST."""
import argparse,collections,hashlib,json,sqlite3,time
from pathlib import Path
import pyarrow.parquet as pq

def main(root):
    (root/'reports').mkdir(exist_ok=True)
    db=sqlite3.connect(root/'manifests/catalog_dedup.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS pairs (kind TEXT, digest TEXT, PRIMARY KEY(kind,digest))')
    db.execute('CREATE TABLE IF NOT EXISTS images (kind TEXT, digest TEXT, PRIMARY KEY(kind,digest))')
    db.execute('DELETE FROM pairs')
    db.execute('DELETE FROM images')
    summary={'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'groups':{},
      'notes':['Provided images include synthetic and reconstructed templates; provenance is retained.',
        'Derived images are rendered from selected SVG or selected first-page drawio code; these counts are separate.',
        'Exact pair deduplication spans sources within each kind. Provided and derived groups are not jointly deduplicated.',
        'Provided-pair completeness is structural; only evaluation samples of provided pairs were independently rendered by this task. Derived images are rendered from their selected code.']}
    sizes={}
    for kind in ('provided','derived'):
        folder=root/('clean' if kind=='provided' else 'derived');folder.mkdir(exist_ok=True)
        dest=folder/'manifest.jsonl';temp=dest.with_suffix('.jsonl.tmp')
        stats={'pairs':0,'distinct_image_files_by_sha256':0,'duplicate_pairs':0,'invalid_locators':0,'quarantined_legacy_mixed_native_pairs':0,'formats':collections.Counter(),
               'categories':collections.Counter(),'sources':collections.Counter()}
        errors=(root/'reports'/('catalog_'+kind+'_errors.jsonl')).open('w')
        aliases=(root/'reports'/('catalog_'+kind+'_duplicate_origins.jsonl')).open('w');origins={}
        paths=[]
        for path in sorted((root/'manifests').glob('*.jsonl')):
            if '.rejected.' in path.name or path.name.endswith('.derived.jsonl'):continue
            is_derived=path.name.startswith('derived.')
            if is_derived != (kind=='derived'):continue
            paths.append(path)
        with temp.open('w') as output:
            for path in paths:
                for line_number,line in enumerate(path.open(),1):
                    if not line.strip():continue
                    try:
                        row=json.loads(line)
                        if row.get('reason') or not row.get('structurally_complete'):continue
                        if kind=='derived' and row.get('format')=='drawio' and row.get('image_provenance')!='rendered_from_selected_native_drawio':
                            stats['quarantined_legacy_mixed_native_pairs']+=1
                            errors.write(json.dumps({'manifest':str(path),'line':line_number,'reason':'legacy SVG image/native XML pair lacks same-code render; excluded from canonical catalog'})+'\n')
                            continue
                        if not row.get('image_sha256') or not row.get('code_sha256'):
                            raise ValueError('missing content hashes')
                        if row.get('clean_file'):
                            f=(root/row['clean_file']).resolve()
                            if not f.is_relative_to(root.resolve()) or not f.is_file():raise ValueError('missing clean parquet')
                            if f not in sizes:sizes[f]=pq.ParquetFile(f).metadata.num_rows
                            if not 0<=row['clean_row']<sizes[f]:raise ValueError('clean row out of bounds')
                        else:
                            image=row.get('reference_image') or row.get('image_file')
                            code=row.get('code_file')
                            if not image or not code or not (root/image).is_file() or not (root/code).is_file():
                                raise ValueError('missing standalone image/code locator')
                        digest=hashlib.sha256((row['image_sha256']+row['code_sha256']).encode()).hexdigest()
                        origin={'source':row.get('source'),'source_manifest':str(path.relative_to(root)),'source_manifest_line':line_number}
                        try:db.execute('INSERT INTO pairs VALUES (?,?)',(kind,digest))
                        except sqlite3.IntegrityError:
                            stats['duplicate_pairs']+=1
                            aliases.write(json.dumps({'pair_sha256':digest,'kept_origin':origins[digest],'additional_origin':origin},ensure_ascii=False)+'\n')
                            continue
                        origins[digest]=origin
                        inserted=db.execute('INSERT OR IGNORE INTO images VALUES (?,?)',(kind,row['image_sha256']))
                        stats['distinct_image_files_by_sha256']+=max(0,inserted.rowcount)
                        row['catalog_kind']=kind;row['pair_sha256']=digest
                        row['alignment_verification']='rendered_from_selected_code' if kind=='derived' else 'provider_declared_pairing_not_independently_rendered'
                        if row.get('source')=='sxy1620348809--VCG-Bench':
                            row['alignment_note']='Reconstructed XML, not pixel-identical author source. Two frozen examples have substantial reference/render differences; see evaluation/dataset_gold_validation/summary.json.'
                        row['source_manifest']=str(path.relative_to(root));row['source_manifest_line']=line_number
                        output.write(json.dumps(row,ensure_ascii=False)+'\n')
                        stats['pairs']+=1
                        for key,field in [('formats','format'),('categories','category'),('sources','source')]:
                            stats[key][row.get(field,'unknown')]+=1
                    except Exception as exc:
                        stats['invalid_locators']+=1
                        errors.write(json.dumps({'manifest':str(path),'line':line_number,'error':type(exc).__name__+': '+str(exc)[:300]})+'\n')
                db.commit()
        temp.replace(dest);errors.close();aliases.close()
        summary['groups'][kind]={k:dict(v) if isinstance(v,collections.Counter) else v for k,v in stats.items()}
        summary['groups'][kind]['manifest']=str(dest)
    summary['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    out=root/'reports/catalog_summary.json';out.write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    db.close();print(json.dumps(summary,ensure_ascii=False),flush=True)
    return int(any(g['invalid_locators'] for g in summary['groups'].values()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();raise SystemExit(main(a.root.resolve()))
