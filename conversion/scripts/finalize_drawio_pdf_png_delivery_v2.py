"""Verify all frozen triplets and produce a payload-only ZIP on HKUST3."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,os,subprocess,zipfile,zlib
from collections import deque

R=Path('/backup/shaoshitong/img2code_20261029')
NAME='drawio_pdf_png_4316_v1';A=R/'conversion'/NAME;D=R/'deliveries'/NAME
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()
def verify(item):
    n,row=item;directory=D/f'{n:06d}';proof=json.loads((A/'proofs'/f'{n:06d}.json').read_text())
    assert proof['ok'] and proof['id']==row['id'] and proof['PDF_compiled_from_native_SVG']
    assert proof['source_code_sha256']==row['code_sha256'] and proof['source_png_sha256']==row['image_sha256']
    assert {f.name for f in directory.iterdir()}=={'diagram.drawio','diagram.png','diagram.pdf'}
    files={}
    for f in sorted(directory.iterdir()):
        h=digest(f);assert h==proof['output_sha256'][f.name]
        files[str(f.relative_to(D))]=dict(sha256=h,bytes=f.stat().st_size)
    assert files[f'{n:06d}/diagram.png']['sha256']==row['image_sha256']
    assert subprocess.run(['pdfinfo',str(directory/'diagram.pdf')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30).returncode==0
    return dict(number=n,id=row['id'],files=files,drawio_bytes_unchanged=proof['drawio_bytes_unchanged'],PDF_render_mode=proof.get('PDF_render_mode','native_vector_PDF'))

def compressed_member(name,meta):
    path=D/name;blob=path.read_bytes();assert hashlib.sha256(blob).hexdigest()==meta['sha256']
    compressor=zlib.compressobj(1,zlib.DEFLATED,-15)
    data=compressor.compress(blob)+compressor.flush()
    info=zipfile.ZipInfo.from_file(path,D.name+'/'+name)
    info.compress_type=zipfile.ZIP_DEFLATED;info.file_size=len(blob);info.compress_size=len(data)
    info.CRC=zlib.crc32(blob)&0xffffffff;info.flag_bits=0
    assert max(info.file_size,info.compress_size)<zipfile.ZIP64_LIMIT
    return info,data

def parallel_zip(temp,files):
    # Deflate independently on HKUST3 CPU threads, then emit standard ZIP local
    # records and let stdlib write ZIP64 central-directory records. Bounded
    # futures retain at most 48 members; every resulting member is read back.
    items=iter(sorted(files));pending=deque()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool,zipfile.ZipFile(temp,'w',allowZip64=True) as z:
        for _ in range(48):
            name=next(items,None)
            if name is not None:pending.append(pool.submit(compressed_member,name,files[name]))
        i=0
        while pending:
            info,data=pending.popleft().result();info.header_offset=z.fp.tell()
            z._writecheck(info);z._didModify=True
            z.fp.write(info.FileHeader(False));z.fp.write(data)
            z.start_dir=z.fp.tell();z.filelist.append(info);z.NameToInfo[info.filename]=info
            i+=1
            name=next(items,None)
            if name is not None:pending.append(pool.submit(compressed_member,name,files[name]))
            if i%1500==0:print(json.dumps(dict(at_utc=now(),archived_files=i,archive_bytes=temp.stat().st_size,compression_workers=16)),flush=True)
def main():
    source=A/'input_snapshot.jsonl';rows=[json.loads(x) for x in source.read_text().splitlines()]
    assert len(rows)==4316 and {f.name for f in D.iterdir()}=={f'{n:06d}' for n in range(1,len(rows)+1)}
    records=[];files={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for record in pool.map(verify,enumerate(rows,1)):
            records.append(record);files.update(record['files'])
            if len(records)%500==0:print(json.dumps(dict(at_utc=now(),verified_pairs=len(records))),flush=True)
    assert len(files)==12948
    (A/'delivery_manifest.json').write_text(json.dumps(dict(source_snapshot_sha256=digest(source),records=records),indent=2)+'\n')
    archive=D.with_suffix('.zip');temp=archive.with_name(archive.name+'.partial')
    parallel_zip(temp,files)
    with zipfile.ZipFile(temp) as z:
        assert len(z.namelist())==len(files)
        for name,meta in files.items():
            h=hashlib.sha256()
            with z.open(D.name+'/'+name) as f:
                for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
            assert h.hexdigest()==meta['sha256'],name
    os.replace(temp,archive)
    receipt=dict(at_utc=now(),state='complete',CPU_host='HKUST3',pairs=len(rows),payload_files=len(files),
        only_extensions=['.drawio','.pdf','.png'],directory=str(D),archive=str(archive),archive_bytes=archive.stat().st_size,
        archive_sha256=digest(archive),source_snapshot_sha256=digest(source),all_payload_checksums_verified=True,
        all_ZIP_member_checksums_verified=True,all_PDFs_reopened=True,PNG_bytes_unchanged=True,
        drawio_source_bytes_unchanged=sum(x['drawio_bytes_unchanged'] for x in records),
        rasterized_filter_PDF_numbers=[x['number'] for x in records if 'lossless_raster' in x['PDF_render_mode']],
        font_note='Author font declarations retained; PDFs use fonts embedded by the pinned offline Chromium runtime.')
    (A/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
