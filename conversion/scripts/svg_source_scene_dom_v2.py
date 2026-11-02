"""Fresh, offline SVG scene metadata with v6-compatible object identities.

``capture_scene(record)`` rechecks original SVG/reference SHA256s under clean
before and after capture, loads the adjacent versioned JS, and returns metadata.
It never writes media, files, jobs, queues or canonical records. Unsupported
source features remain explicit ``issues``; this is extraction, not acceptance.

Object fields: sceneAncestry refs -> sceneMetadata.ancestors; sceneGroupRoles;
sceneComputedCss; sceneAncestorOpacity; sceneUseContexts/sceneMarkerContexts;
sceneGeometry (screen samples and source-local fontTools topology); sceneImage.
Expanded markers retain markerOwner and add markerSide, markerDefinitionId and
markerContext. markerContexts describe synthetic clones, never falsely claiming
that a clone has applied the original SVG marker viewport clip.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading
import urllib.parse
from collections import Counter

ROOT=Path(os.environ.get('IMG2CODE_ROOT','/backup/shaoshitong/img2code_20261029')).resolve()
CHROMIUM=os.environ.get('IMG2CODE_CHROMIUM','/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome')
EXTRACTOR=Path(__file__).with_name('svg_dom_source_scene_v2.js')
POLICY='fresh_svg_source_scene_analytic_endpoint_v2'
_runtime=threading.local()
sha=lambda blob:hashlib.sha256(blob).hexdigest()


class SceneCaptureError(ValueError):
    pass


def _checked_clean(relative,digest):
    if not isinstance(relative,str) or not relative:raise SceneCaptureError('missing_source_payload_locator')
    if not isinstance(digest,str) or len(digest)!=64:raise SceneCaptureError('missing_source_payload_sha256')
    path=(ROOT/relative).resolve()
    if not path.is_relative_to(ROOT/'clean'):raise SceneCaptureError('source_payload_outside_clean: '+relative)
    blob=path.read_bytes()
    if sha(blob)!=digest:raise SceneCaptureError('source_payload_hash_mismatch: '+relative)
    return blob


def _browser():
    if not hasattr(_runtime,'browser'):
        from playwright.sync_api import sync_playwright
        _runtime.driver=sync_playwright().start()
        _runtime.browser=_runtime.driver.chromium.launch(executable_path=CHROMIUM,args=['--disable-dev-shm-usage'])
    return _runtime.browser


def close_worker_runtime():
    """Release this thread's reusable browser when a batch worker exits."""
    if hasattr(_runtime,'browser'):
        try:_runtime.browser.close()
        finally:
            _runtime.driver.stop()
            _runtime.__dict__.clear()


def _issue(dom,reason,**detail):
    value={'reason':reason,'severity':'unsupported','scope':'source_paint',**detail}
    dom.setdefault('issues',[]).append(value);dom.setdefault('sceneIssues',[]).append(value)


def enrich_scene(dom):
    """Add authoritative source-local path closure and image header metadata."""
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.svgLib.path import parse_path
    from svg_convert_v2 import path_for
    for obj in dom.get('objects',[]):
        if obj.get('type')=='shape':
            try:
                pen=RecordingPen();parse_path(path_for(obj),pen);subpaths=[];current=None;counts=Counter()
                for op,points in pen.value:
                    counts[op]+=1
                    if op=='moveTo':
                        if current is not None:subpaths.append(current)
                        current={'closed':False,'operations':[]}
                    elif current is None:current={'closed':False,'implicit_start':True,'operations':[]}
                    current['operations'].append({'operation':op,'points':[[float(x),float(y)] for x,y in points]})
                    if op in ('closePath','endPath'):
                        current['closed']=op=='closePath';subpaths.append(current);current=None
                if current is not None:subpaths.append(current)
                style=obj['style'];visible_fill=style.get('fill')!='none' and float(style.get('fillOpacity',1))*float(style.get('opacity',1))>0
                visible_stroke=style.get('stroke')!='none' and float(style.get('strokeWidth',0))>0 and float(style.get('strokeOpacity',1))*float(style.get('opacity',1))>0
                closed=sum(part['closed'] for part in subpaths);opened=len(subpaths)-closed
                topology={'parser':'fontTools.svgLib.path.parse_path/RecordingPen','coordinate_space':'source_local','subpath_count':len(subpaths),'closed_subpaths':closed,'open_subpaths':opened,'all_subpaths_explicitly_closed':bool(subpaths) and opened==0,'visible_fill':visible_fill,'visible_stroke':visible_stroke,'has_open_stroke':bool(opened and visible_stroke),'fill_implicitly_closes_open_subpaths':bool(opened and visible_fill),'operation_counts':dict(counts),'subpaths':subpaths,'has_curves':bool(counts['curveTo'] or counts['qCurveTo']),'empty_geometry':not bool(counts['lineTo'] or counts['curveTo'] or counts['qCurveTo'])}
                obj.setdefault('sceneGeometry',{})['topology']=topology
            except Exception as error:
                obj.setdefault('sceneGeometry',{})['topology']={'parser':'fontTools.svgLib.path.parse_path/RecordingPen','error':repr(error),'complete':False}
                _issue(dom,'scene_source_path_parse_failed',id=obj.get('id'),error=repr(error)[:800])
        elif obj.get('type')=='image':
            info=obj.setdefault('sceneImage',{});href=obj.get('href','')
            try:
                assert href.startswith('data:image/'),'external_image'
                header,payload=href.split(',',1);mime=header.split(';',1)[0][5:].lower();blob=base64.b64decode(payload,validate=True) if ';base64' in header.lower() else urllib.parse.unquote_to_bytes(payload)
                info.update(mime=mime,bytes_sha256=sha(blob),encoded_bytes=len(blob),is_raster='svg' not in mime)
                if 'svg' in mime:
                    info['kind']='vector_data_uri';_issue(dom,'scene_vector_image_requires_editable_expansion',id=obj.get('id'));continue
                from PIL import Image
                image=Image.open(io.BytesIO(blob));size=list(image.size);frames=int(getattr(image,'n_frames',1));info.update(kind='original_raster_asset',intrinsic_size=size,format=image.format,frames=frames)
                if frames!=1:_issue(dom,'scene_animated_raster_asset_unproven',id=obj.get('id'),frames=frames)
                attrs=info.get('attrs',{});w,h=float(attrs.get('width',0)),float(attrs.get('height',0));ratio_matches=bool(w>0 and h>0 and abs(w/h-size[0]/size[1])<=1e-6*max(1,abs(w/h),abs(size[0]/size[1])));info['intrinsic_ratio_matches_viewport']=ratio_matches
                if info.get('preserveAspectRatio','xMidYMid meet').strip()!='none' and not ratio_matches:_issue(dom,'scene_image_aspect_mapping_unproven',id=obj.get('id'),preserveAspectRatio=info.get('preserveAspectRatio'),viewport=[w,h],intrinsic_size=size)
                if info.get('flipX') or info.get('flipY'):_issue(dom,'scene_image_axis_flip_not_in_base_mapping',id=obj.get('id'),flipX=info.get('flipX'),flipY=info.get('flipY'))
            except Exception as error:
                info['decode_error']=repr(error);_issue(dom,'scene_original_image_header_unproven',id=obj.get('id'),error=repr(error)[:800])
    return dom


def capture_scene(record):
    """Return this source revision's fresh DOM; no stored converter flags trusted.

    External resources are aborted and reported as unsupported issues, allowing
    the caller to aggregate reasons while preventing a complete-coverage claim.
    ``sceneCapture.completeOfflineSource`` must be true for an accepting profile.
    Existing v6 issues are always retained alongside the additive scene issues.
    """
    from PIL import Image
    if record.get('source_format') not in (None,'svg'):raise SceneCaptureError('scene_capture_requires_direct_svg_source')
    code=_checked_clean(record.get('original_source_code'),record.get('source_code_sha256'))
    reference=_checked_clean(record.get('original_reference'),record.get('source_image_sha256'))
    width,height=Image.open(io.BytesIO(reference)).size
    if min(width,height)<=0:raise SceneCaptureError('invalid_reference_dimensions')
    extractor=EXTRACTOR.read_bytes();extractor_hash=sha(extractor);blocked=[]
    browser=_browser();context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block')
    try:
        def reject(route):blocked.append(route.request.url);route.abort()
        context.route('**/*',reject);page=context.new_page();page.set_default_timeout(45000)
        page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code.decode('utf-8'),wait_until='load')
        page.evaluate("""([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('missing source SVG');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}""",[width,height])
        page.evaluate('document.fonts.ready');from svg_source_endpoint_bridge_v1 import capture;dom=capture(page)
    finally:context.close()
    if sha(EXTRACTOR.read_bytes())!=extractor_hash:raise SceneCaptureError('extractor_changed_during_capture')
    _checked_clean(record['original_source_code'],record['source_code_sha256']);_checked_clean(record['original_reference'],record['source_image_sha256'])
    if blocked:_issue(dom,'scene_external_resources_blocked',urls=sorted(set(blocked)))
    enrich_scene(dom)
    dom['sceneCapture']={'policy':POLICY,'version':1,'recordId':record.get('id'),'recordCodeSha256':record.get('code_sha256'),'sourceCodeSha256':record['source_code_sha256'],'sourceImageSha256':record['source_image_sha256'],'referenceSize':[width,height],'extractorSha256':extractor_hash,'moduleSha256':sha(Path(__file__).read_bytes()),'browserVersion':browser.version,'sourcePayloadHashesRecheckedAfterCapture':True,'completeOfflineSource':not bool(blocked),'blockedResources':sorted(set(blocked)),'objectIdsV6Compatible':True,'acceptanceNotImplied':True,'domSha256':sha(json.dumps(dom,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())}
    return dom
