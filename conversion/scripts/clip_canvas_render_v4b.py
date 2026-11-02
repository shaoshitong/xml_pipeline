"""Fresh clip/text evidence joined to a separately proved strict native canvas.

render has the seven positional arguments of native_job. Non-clip renderers
pass through unchanged. A clip render is usable only when its PNG, page and
actual text/fonts agree exactly with a second real paintbounds-strict render.
All attempted clip proofs remain in this module's HKUST-owned audit directory.
"""
import copy
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import time
import uuid

from strict_canvas_gate import require_declared_page

R=Path('/backup/shaoshitong/img2code_20261029')
W=R/'conversion'
CLIP_RENDERER=W/'rendering_clipbox_strict/remote_render.py'
STRICT_RENDERER=W/'rendering_paintbounds_strict/remote_render.py'
OWNER='conversion/clip_canvas_render_v4b'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def _native_job(*args):
    from native_worker import native
    return native.native_job(*args)


def _json(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()


def _save(work,name,raw):
    path=work/name
    with path.open('xb') as stream:stream.write(raw)
    return {'file':str(path.relative_to(R)),'sha256':sha(raw)}


def _pin(path):
    path=Path(path).resolve()
    return {'file':str(path),'sha256':sha(path.read_bytes())}


def _number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Nonfinite/invalid actual text geometry')
    return float(value)


def font_signature(info):
    rows=info['actual_platform_font_usage'];result={}
    if not isinstance(rows,list):raise ValueError('Actual physical font rows missing')
    for row in rows:
        cell=str(row['cell'])
        if cell in result:raise ValueError('Duplicate physical font cell')
        fonts={}
        for font in row['fonts']:
            count=font['glyphCount']
            if isinstance(count,bool) or not isinstance(count,int) or count<0:raise ValueError('Invalid actual glyph count')
            if not count:continue
            if not isinstance(font.get('postScriptName'),str) or not font['postScriptName']:raise ValueError('Missing physical font name')
            if not isinstance(font.get('isCustomFont'),bool):raise ValueError('Missing actual custom-font identity')
            family=font.get('familyName')
            if not isinstance(family,str) or not family:raise ValueError('Missing physical font family')
            key=(font['postScriptName'],font['isCustomFont'],family);fonts[key]=fonts.get(key,0)+count
        result[cell]=sorted([list(key)+[count] for key,count in fonts.items()])
    return result


def text_signature(info):
    rows=info['actual_text_positions'];result={}
    if not isinstance(rows,list):raise ValueError('Actual text positions missing')
    for row in rows:
        cell=str(row['cell'])
        if cell in result:raise ValueError('Duplicate actual text cell')
        runs=[]
        for run in row['runs']:
            text=run['text']
            if not isinstance(text,str):raise ValueError('Invalid actual logical text')
            style={key:run[key] for key in ('font','fontKerning','fontFeatureSettings','letterSpacing','lineHeight')}
            if not all(isinstance(value,str) for value in style.values()):raise ValueError('Missing actual text CSS style')
            chars=[]
            for char in run['chars']:
                if not isinstance(char['text'],str):raise ValueError('Invalid actual grapheme')
                chars.append({'text':char['text'],**{key:_number(char[key]) for key in ('x','y','width','height')}})
            if ''.join(char['text'] for char in chars)!=text:raise ValueError('Actual graphemes do not cover logical text')
            optional={key:run[key] for key in ('baseline','fontSize','fontWeight','fontStyle','fontStretch','fontVariationSettings','fontVariations','wordSpacing','direction','writingMode','transform','clip','clipBox') if key in run}
            runs.append({'text':text,**style,**optional,'chars':chars})
        result[cell]=runs
    return result


def _page(info,width,height,clip=False):
    if info['selected_image']!='declared_first_page':raise ValueError('Renderer selected a cropped/tight page')
    if info['output_size']!=[width,height] or info['canvas']!=[width,height]:raise ValueError('Renderer canvas/output mismatch')
    if info['content_outside_declared_canvas'] is not False:raise ValueError('Renderer reports native content outside page')
    if clip and info['native_graph_bounds_outside_declared_canvas'] is not False:
        raise ValueError('Old clip renderer reports graph bounds outside page')


def _png_page(raw,width,height):
    if (not isinstance(raw,bytes) or len(raw)<33 or raw[:8]!=b'\x89PNG\r\n\x1a\n'
            or raw[12:16]!=b'IHDR' or struct.unpack('>II',raw[16:24])!=(width,height)):
        raise ValueError('PNG canvas/encoding differs from the declared page')


def _runtime(info,manifest_pin):
    if info['runtime_cache_manifest_sha256']!=manifest_pin['sha256']:raise ValueError('Renderer runtime manifest is not current/pinned')
    keys=('runtime_cache_manifest_sha256','runtime_cache_id','viewer_bundle_sha256','runtime_cache_provenance')
    result={key:info[key] for key in keys}
    if not result['runtime_cache_id'] or not isinstance(result['runtime_cache_provenance'],dict):raise ValueError('Runtime identity missing')
    bundle=result['viewer_bundle_sha256']
    if not isinstance(bundle,str) or len(bundle)!=64 or any(c not in '0123456789abcdef' for c in bundle):raise ValueError('Runtime viewer bundle identity missing')
    return result


def render(xml,width,height,timeout,renderer,maxsize,manifest):
    if Path(renderer).resolve()!=CLIP_RENDERER.resolve():
        return _native_job(xml,width,height,timeout,renderer,maxsize,manifest)
    started=time.monotonic();work=None;artifacts={};pins={}
    try:
        if not isinstance(xml,str) or not xml:raise ValueError('Missing current XML')
        if any(isinstance(v,bool) or not isinstance(v,int) or v<=0 for v in (width,height,maxsize)) or max(width,height)>maxsize:
            raise ValueError('Invalid/unscaled current page')
        pins={'clip_renderer':_pin(CLIP_RENDERER),'strict_renderer':_pin(STRICT_RENDERER),'runtime_manifest':_pin(manifest),
              'adapter':_pin(__file__),'strict_canvas_gate':_pin(Path(__file__).with_name('strict_canvas_gate.py'))}
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex
        work=R/OWNER/sha(xml.encode())/stamp;work.mkdir(parents=True,exist_ok=False)
        artifacts['xml']=_save(work,'input.drawio',xml.encode())
        artifacts['request']=_save(work,'request.json',_json({'width':width,'height':height,'timeout':timeout,'maxsize':maxsize,'pins':pins}))
        clip=_native_job(xml,width,height,timeout,CLIP_RENDERER,maxsize,manifest)
        if not clip.get('ok'):raise ValueError('Clip renderer failed: '+str({k:v for k,v in clip.items() if k!='png'})[:1800])
        clip_info=clip['native_render'];artifacts['clip_info']=_save(work,'clip.native_render.json',_json(clip_info));artifacts['clip_png']=_save(work,'clip.png',clip['png'])
        _page(clip_info,width,height,clip=True);_png_page(clip['png'],width,height)
        if not isinstance(clip_info['actual_clip_boxes'],list):raise ValueError('Actual clip evidence missing')
        # If an old clip path did perform a padded audit, it must also pass.
        if 'outside_page_pixel_audit' in clip_info:require_declared_page(clip_info,width,height)
        clip_runtime=_runtime(clip_info,pins['runtime_manifest'])
        clip_fonts=font_signature(clip_info);clip_text=text_signature(clip_info)
        paint=_native_job(xml,width,height,timeout,STRICT_RENDERER,maxsize,manifest)
        if not paint.get('ok'):raise ValueError('Paintbounds strict renderer failed: '+str({k:v for k,v in paint.items() if k!='png'})[:1800])
        paint_info=paint['native_render'];artifacts['strict_info']=_save(work,'strict.native_render.json',_json(paint_info));artifacts['strict_png']=_save(work,'strict.png',paint['png'])
        _page(paint_info,width,height);_png_page(paint['png'],width,height);require_declared_page(paint_info,width,height)
        boundary=paint_info['outside_page_pixel_audit']
        if boundary.get('audit_always_performed') is not True or boundary.get('minimum_probe_margin')!=32 or paint_info.get('probe_includes_actual_dom_paint_bounds') is not True:
            raise ValueError('Strict renderer lacks unconditional real padded/DOM paint proof')
        offset=boundary['offset'];padded=boundary['padded_native_render_size']
        if (len(offset)!=2 or len(padded)!=2 or any(type(n) is not int for n in offset+padded)
                or min(offset)<32 or padded[0]<width+offset[0]+32 or padded[1]<height+offset[1]+32):
            raise ValueError('Padded native probe does not cover the full original page')
        if (clip_info['scale'],clip_info['translate'])!=(paint_info['scale'],paint_info['translate']):raise ValueError('Clip/strict native page scale/origin differs')
        if clip['png']!=paint['png']:raise ValueError('Clip and strict native PNG bytes differ')
        if clip_runtime!=_runtime(paint_info,pins['runtime_manifest']):raise ValueError('Clip/strict runtime identities differ')
        paint_fonts=font_signature(paint_info);paint_text=text_signature(paint_info)
        if clip_fonts!=paint_fonts:raise ValueError('Clip/strict actual physical fonts/glyph counts differ')
        if clip_text!=paint_text:raise ValueError('Clip/strict actual logical text/CSS/grapheme positions differ')
        for entry in pins.values():
            if sha(Path(entry['file']).read_bytes())!=entry['sha256']:raise ValueError('Pinned renderer/runtime/adapter changed during rendering')
        for name,entry in artifacts.items():
            if sha((R/entry['file']).read_bytes())!=entry['sha256']:raise ValueError('Fresh '+name+' audit artifact changed')
        proof={'version':1,'method':'independent_clip_and_unconditional_strict_canvas_native_render_v4b','code_sha256':sha(xml.encode()),
            'png_sha256':sha(clip['png']),'canvas':[width,height],'pins':pins,'runtime':clip_runtime,'artifacts':artifacts,
            'png_byte_identical':True,'canvas_identical':True,'old_clip_overflow_rejected':True,
            'actual_font_signature_sha256':sha(_json(clip_fonts)),'actual_text_signature_sha256':sha(_json(clip_text)),
            'outside_page_pixel_audit':copy.deepcopy(boundary),'accepted':False,'model_calls':0}
        proof_entry=_save(work,'proof.json',_json(proof))
        combined=copy.deepcopy(clip_info);combined['outside_page_pixel_audit']=copy.deepcopy(boundary)
        combined['clip_canvas_strict_proof_v4b']={**proof_entry,'code_sha256':proof['code_sha256'],'png_sha256':proof['png_sha256'],'clip_renderer_sha256':pins['clip_renderer']['sha256'],'strict_renderer_sha256':pins['strict_renderer']['sha256'],'runtime_manifest_sha256':pins['runtime_manifest']['sha256']}
        require_declared_page(combined,width,height)
        _save(work,'combined.native_render.json',_json(combined))
        return {**clip,'native_render':combined,'seconds':time.monotonic()-started,'clip_canvas_strict_audit':proof_entry}
    except Exception as exc:
        error={'ok':False,'reason':'clip_canvas_strict_bridge_rejected','error_type':type(exc).__name__,'error':str(exc)[:2500],
               'seconds':time.monotonic()-started,'code_sha256':sha(xml.encode()) if isinstance(xml,str) else None,'pins':pins,'artifacts':artifacts}
        if work is not None:
            try:error['clip_canvas_strict_audit']=_save(work,'rejected.json',_json(error))
            except OSError:pass
        return error
