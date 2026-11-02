"""Compile an immutable original through a separate option-forwarding entry point."""
import hashlib,json,shutil,sys
from pathlib import Path
from native_worker import R,W,now
from tex_xcolor_forwarding import plan
import tectonic_compile
from tex_missing_v2 import missing_files
tectonic_compile.missing_files=missing_files
sys.path.append(str(W/'runtime/python_packages'));import pymupdf

def sha(data):return hashlib.sha256(data).hexdigest()

def compile_source(directory,data):
    proof=plan(data);directory.mkdir(parents=True,exist_ok=True)
    (directory/'source.tex').write_bytes(data)
    build=directory/'build';build.mkdir(exist_ok=True);(build/'original_source.tex').write_bytes(data);(build/'source.tex').write_text(proof['wrapper'])
    r,attempts=tectonic_compile.compile_case(build)
    proof.update(at=now(),compile_attempts=attempts,compile_returncode=r.returncode,sandbox='Original source and wrapper compiled by offline Tectonic under existing bwrap resource/network isolation')
    (directory/'stdout.log').write_text(r.stdout);(directory/'stderr.log').write_text(r.stderr)
    assert sha((directory/'source.tex').read_bytes())==proof['original_code_sha256']
    assert sha((build/'original_source.tex').read_bytes())==proof['original_code_sha256']
    assert sha((build/'source.tex').read_bytes())==proof['wrapper_sha256']
    (directory/'forwarding_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    if r.returncode:raise ValueError('xcolor forwarding compile failed: '+r.stderr[-2200:])
    pdf=build/'source.pdf';assert pdf.exists();shutil.copyfile(pdf,directory/'source.pdf')
    proof['pdf_sha256']=sha(pdf.read_bytes())
    with pymupdf.open(pdf) as doc:
        assert len(doc)>0;proof['pages']=[{'page':i,'text_characters':len(p.get_text()),'drawing_paths':len(p.get_drawings()),'images':len(p.get_images())} for i,p in enumerate(doc)]
        assert all(p['text_characters'] or p['drawing_paths'] or p['images'] for p in proof['pages']),'blank page'
    (directory/'forwarding_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof
