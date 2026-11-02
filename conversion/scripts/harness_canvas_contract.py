"""Pin a proven page expansion; it never certifies a later model's graph fidelity."""
import hashlib,io,json,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W
from native_page_padding import shift
from native_padding_proof import verify_cells,exact_pixel_proof
from strict_canvas_gate import require_declared_page
sha=lambda b:hashlib.sha256(b).hexdigest()
RENDERER=W/'rendering_canvas_padding_proof/remote_render.py'

def read_owned(value):
    p=(R/value).resolve();assert p.is_relative_to(W/'native_page_padding'),'Unowned padding audit path';return p

def validate(previous,reference):
    inherited=previous.get('native_canvas_contract')
    if inherited:
        origin=read_owned(inherited['origin_record']);raw=origin.read_bytes();assert sha(raw)==inherited['origin_record_sha256'],'Padding origin record changed'
    else:
        proof=previous['native_page_padding'];origin=read_owned(proof['audit']).parent/'candidate_record.json';raw=origin.read_bytes()
    r=json.loads(raw);p=r['native_page_padding'];folder=origin.parent
    assert all(r[k]==previous[k] for k in ('id','source_image_sha256','source_code_sha256')),'Canvas source identity mismatch'
    assert sha(reference)==r['source_image_sha256'],'Original image changed'
    old=json.loads((folder/'before_record.json').read_text());oldxml=(folder/'baseline/input.drawio').read_text() if (folder/'baseline/input.drawio').exists() else None
    # The immutable baseline archive belongs to this exact source and code revision.
    from harness_source_provenance import archive_record
    archived,oldbytes,_,_=archive_record(r['previous_candidate_archive'],r);oldxml=oldbytes.decode()
    assert archived==old and sha(oldbytes)==p['old_code_sha256'],'Padding baseline changed'
    xml=(folder/'candidate.drawio').read_text();png=(folder/'candidate.png').read_bytes()
    assert sha(xml.encode())==r['code_sha256']==p['new_code_sha256'] and sha(png)==r['image_sha256']==p['new_image_sha256'],'Padding candidate changed'
    g=p['geometry'];dx,dy=g['translation'];nw,nh=g['new_page'];assert list(Image.open(io.BytesIO(reference)).size)==g['old_page'],'Padding is not registered to original canvas'
    expected,geometry=shift(oldxml,dx,dy,nw,nh);assert expected==xml and geometry==g,'Unverified page transformation';verify_cells(oldxml,xml,g)
    oldinfo=json.loads((folder/'baseline/native_render.json').read_text());newinfo=json.loads((folder/'candidate/native_render.json').read_text())
    assert newinfo==r['render'];require_declared_page(newinfo,nw,nh)
    assert sha(RENDERER.read_bytes())==newinfo['renderer_module_sha256'],'Pinned renderer changed'
    assert newinfo['renderer_profile']=='native_page_padding_strict_v1'
    exact=exact_pixel_proof(folder/'baseline',folder/'candidate',oldinfo,newinfo,p['canvas_plan']);assert exact==p['exact_pixel_proof']
    contract={'version':1,'origin_record':str(origin.relative_to(R)),'origin_record_sha256':sha(raw),'origin_code_sha256':r['code_sha256'],'origin_image_sha256':r['image_sha256'],'source_image_sha256':r['source_image_sha256'],'source_code_sha256':r['source_code_sha256'],'reference_page':g['old_page'],'output_page':g['new_page'],'original_page_offset':g['translation'],'renderer_profile':newinfo['renderer_profile'],'renderer_module_sha256':newinfo['renderer_module_sha256'],'scope':'Fixed page dimensions derived from an exact source-page/native-paint preserving baseline. Later graph revisions require independent fidelity and editability validation.'}
    if inherited:assert inherited==contract,'Inherited canvas contract changed'
    else:assert previous['code_sha256']==r['code_sha256'] and previous['image_sha256']==r['image_sha256'],'Padding proof does not describe current baseline'
    return contract

def require_xml_page(xml,contract):
    models=list(E.fromstring(xml).iter('mxGraphModel'));assert len(models)==1
    assert [float(models[0].get(k,'nan')) for k in ('pageWidth','pageHeight')]==contract['output_page'],'Model changed approved page dimensions'
    return True

def require_render(render,contract):
    require_declared_page(render,*contract['output_page'])
    assert render['renderer_profile']==contract['renderer_profile'] and render['renderer_module_sha256']==contract['renderer_module_sha256'],'Native renderer contract changed'
    return True
