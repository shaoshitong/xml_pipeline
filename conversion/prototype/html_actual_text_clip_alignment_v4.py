"""Prototype fixed-global-clip glyph translations, independent of live QA3 pins.

Keep mxGeometry and the existing canonical outer CSS clip byte-for-byte. Move
only its inner inline glyph span by the uniform source/native Range delta.
Actual native clip reference boxes must stay fixed and equal fresh source CSS
clip intersections. Native PNG mask evidence is an additional exact gate.
"""
import copy
import math
import re
import xml.etree.ElementTree as E
from html_actual_text_alignment import analyze,_plain,_style,sha,POSITION_TOLERANCE
from html_actual_text_registration import _signature

OUTER=re.compile(r'^(<span style="clip-path:inset\(([^)]+)\);">)([\s\S]*)(</span>)$')


def source_rectangle(obj,viewport,offset=(0,0)):
    clip=obj.get('sourceClip',{});assert clip.get('partial') and not clip.get('unmodeled'),'Unproved or nonrectangular source clipping'
    chain=clip['chain'];assert chain,'Source clip chain missing'
    for ancestor in chain:
        assert all(float(str(value).removesuffix('px'))==0 for value in ancestor['radius']),'Rounded source clipping needs its own geometry/mask adapter'
    bounds=[max([0]+[e['left'] for e in chain if e['clipX']]),max([0]+[e['top'] for e in chain if e['clipY']]),min([viewport[0]]+[e['right'] for e in chain if e['clipX']]),min([viewport[1]]+[e['bottom'] for e in chain if e['clipY']])]
    assert bounds[2]>bounds[0] and bounds[3]>bounds[1],'Empty source clip'
    return [bounds[0]+offset[0],bounds[1]+offset[1],bounds[2]+offset[0],bounds[3]+offset[1]]


def native_rectangle(clip):
    assert len(clip['fragments'])==1,'A native inline clip has multiple reference fragments'
    match=re.fullmatch(r'inset\(([^)]+)\)',clip['clipPath']);assert match,'Only a rectangular inset mask is supported'
    values=[]
    for value in match[1].split():
        assert re.fullmatch(r'[-+]?(?:\d+\.?\d*|\.\d+)px',value),'Unsupported percentage/rounded native clip'
        values.append(float(value[:-2]))
    assert 1<=len(values)<=4
    if len(values)==1:values*=4
    elif len(values)==2:values=values*2
    elif len(values)==3:values+=[values[1]]
    top,right,bottom,left=values
    return [clip['x']+left,clip['y']+top,clip['x']+clip['width']-right,clip['y']+clip['height']-bottom]


def _clip_rows(info):return {row['cell']:row['clips'] for row in info.get('actual_clip_boxes',[])}
def _canonical(xml):return E.canonicalize(xml)


def propose_clip_locked(xml,dom,native_info,viewport,offset=(0,0),cells=None):
    assert abs(float(native_info.get('scale',1))-1)<1e-9,'Fixed CSS clip proof requires actual native scale one'
    analysis=analyze(dom,native_info,xml,offset);objects={str(obj['id']+1):obj for obj in dom['objects'] if obj['type']=='text'};clips=_clip_rows(native_info)
    root=E.fromstring(xml);cells_by_id={cell.get('id'):cell for cell in root.iter('mxCell')};changes=[];unsupported=[]
    for row in analysis['objects']:
        if row['category']!='uniform_translation_requires_fixed_clip' or cells is not None and row['cell'] not in cells:continue
        key=row['cell'];cell=cells_by_id[key];obj=objects[key]
        try:
            assert _style(cell).get('rotation','0') in ('0','0.0'),'Rotated text needs a transformed CSS coordinate adapter'
            bounds=source_rectangle(obj,viewport,offset);before=cell.get('value','');match=OUTER.fullmatch(before);assert match,'Existing clip is not the canonical single source-rectangular wrapper'
            assert len(clips.get(key,[]))==1,'Missing or ambiguous actual native clip reference box'
            actual=clips[key][0];assert actual['text']==obj['text'],'Actual native clip text changed'
            measured=native_rectangle(actual);assert all(abs(a-b)<=.03 for a,b in zip(measured,bounds)),'Existing native global clip differs from fresh source CSS intersection'
            delta=row['translation'];prefix='<span data-img2code-clip-glyph-offset="v4" style="position:relative;left:'+format(delta['dx'],'.10g')+'px;top:'+format(delta['dy'],'.10g')+'px;">'
            value=match[1]+prefix+match[3]+'</span>'+match[4];assert _plain(value)==_plain(before)
            cell.set('value',value);changes.append({'cell':key,'before_value':before,'after_value':value,'source_clip_bounds':bounds,'native_before_clip_bounds':measured,'native_before_reference_box':{name:actual[name] for name in ('x','y','width','height')},'range_delta':delta,'source_physical_face':row['source_faces'][0],'source_font_size':row['source_font_size'],'maximum_uniform_range_residual':row['maximum_residual_from_translation'],'geometry_unchanged':True,'source_clip':obj['sourceClip']})
        except AssertionError as error:unsupported.append({'cell':key,'reason':str(error)})
    candidate=E.tostring(root,encoding='unicode');restored=E.fromstring(candidate);changed={row['cell']:row for row in changes}
    for cell in restored.iter('mxCell'):
        if cell.get('id') in changed:cell.set('value',changed[cell.get('id')]['before_value'])
    assert _canonical(E.tostring(restored,encoding='unicode'))==_canonical(xml),'A non-glyph-span graph/shape/font/geometry/asset/clip change occurred'
    return candidate,{'version':4,'input_code_sha256':sha(xml.encode()),'output_code_sha256':sha(candidate.encode()),'changes':changes,'unsupported':unsupported,'unchanged_geometry_fonts_assets_and_outer_clip':True,'position_parameters_from_actual_ranges_only':True,'accepted':False}


def verify_clip_locked(before_xml,current_xml,proof,dom,before,after,viewport,offset=(0,0)):
    expected,replayed=propose_clip_locked(before_xml,dom,before,viewport,offset,{row['cell'] for row in proof['changes']})
    assert _canonical(expected)==_canonical(current_xml) and replayed['changes']==proof['changes'],'Clip-glyph transformation/proof changed'
    changed={row['cell']:row for row in proof['changes']};actual=_clip_rows(after);glyphs={row['cell']:row for row in analyze(dom,after,current_xml,offset)['objects']};evidence=[]
    for key,change in changed.items():
        assert glyphs[key]['category']=='actual_glyphs_aligned','Current clipped actual glyphs do not match source Ranges'
        assert len(actual.get(key,[]))==1,'Current clip is missing or duplicated'
        row=actual[key][0];bounds=native_rectangle(row)
        assert all(abs(a-b)<=.03 for a,b in zip(bounds,change['source_clip_bounds'])),'Global source clip moved with the glyph'
        assert all(abs(row[name]-value)<=.03 for name,value in change['native_before_reference_box'].items()),'Native clip reference box moved or changed size'
        evidence.append({'cell':key,'actual_clip_bounds':bounds,'source_clip_bounds':change['source_clip_bounds'],'every_actual_glyph_matches_source':True,'fixed_reference_box':True})
    from html_text_layout_registration_v5 import require_same_actual_positions
    require_same_actual_positions({'actual_text_positions':[row for row in before['actual_text_positions'] if row['cell'] not in changed]},{'actual_text_positions':[row for row in after['actual_text_positions'] if row['cell'] not in changed]})
    old={row['cell']:_signature(row['fonts']) for row in before['actual_platform_font_usage']};new={row['cell']:_signature(row['fonts']) for row in after['actual_platform_font_usage']}
    assert old==new,'Any original physical face or glyph count changed'
    assert all(font.get('isCustomFont') for row in after['actual_platform_font_usage'] for font in row['fonts'] if font.get('glyphCount',0)),'Unembedded actual font'
    return {'ok':True,'changed_cells':sorted(changed),'clips':evidence,'all_original_physical_faces_and_glyph_counts_preserved':True,'all_other_graph_and_outer_clip_markup_unchanged':True}


def diagnostic_variants(xml,cells):
    """Unclipped and no-target background renders, never publication candidates."""
    unclipped=E.fromstring(xml);background=E.fromstring(xml)
    for cell in unclipped.iter('mxCell'):
        if cell.get('id') in cells:
            value=cell.get('value','');match=OUTER.fullmatch(value);assert match
            cell.set('value','<span style="clip-path:none;">'+match[3]+'</span>')
    for cell in background.iter('mxCell'):
        if cell.get('id') in cells:cell.set('value','')
    return E.tostring(unclipped,encoding='unicode'),E.tostring(background,encoding='unicode')


def disjoint_clip_groups(proof,info,margin=4):
    positions={row['cell']:[char for run in row['runs'] for char in run['chars']] for row in info['actual_text_positions']};groups=[]
    for change in proof['changes']:
        chars=positions[change['cell']];box=[min(c['x'] for c in chars)-margin,min(c['y'] for c in chars)-margin,max(c['x']+c['width'] for c in chars)+margin,max(c['y']+c['height'] for c in chars)+margin];entry={**change,'influence_box':box}
        for group in groups:
            if all(min(box[2],other['influence_box'][2])<=max(box[0],other['influence_box'][0]) or min(box[3],other['influence_box'][3])<=max(box[1],other['influence_box'][1]) for other in group):group.append(entry);break
        else:groups.append([entry])
    return groups


def pixel_mask_proof(candidate_png,unclipped_png,background_png,group):
    import io,numpy as np
    from PIL import Image
    arrays=[np.array(Image.open(io.BytesIO(blob)).convert('RGB')) for blob in (candidate_png,unclipped_png,background_png)];candidate,unclipped,background=arrays;assert candidate.shape==unclipped.shape==background.shape
    height,width=candidate.shape[:2];mask=np.zeros((height,width),dtype=bool);x=np.arange(width)+.5;y=np.arange(height)+.5
    for row in group:
        left,top,right,bottom=row['source_clip_bounds'];assert all(abs(v-round(v))<1e-8 for v in (left,top,right,bottom)),'Fractional CSS clip edges need a browser raster mask adapter'
        box=row['influence_box'];mask|=(x[None,:]>=max(left,math.floor(box[0])))&(x[None,:]<min(right,math.ceil(box[2])))&(y[:,None]>=max(top,math.floor(box[1])))&(y[:,None]<min(bottom,math.ceil(box[3])))
    expected=background.copy();expected[mask]=unclipped[mask];mismatch=int(np.any(candidate!=expected,axis=2).sum())
    return {'ok':mismatch==0,'actual_pixel_mismatches':mismatch,'source_clip_reference_mask_verified':mismatch==0,'cells':[row['cell'] for row in group],'integer_global_clip_edges':True,'whole_native_canvas_checked':True}


def rollback_pixel_proof(original_png,all_candidate_png,retained_png,before_info,all_info,rejected,margin=4):
    """Transfer existing clip-mask proofs only through an exact pixel rollback."""
    import io,numpy as np
    from PIL import Image
    original,full,retained=[np.array(Image.open(io.BytesIO(blob)).convert('RGB')) for blob in (original_png,all_candidate_png,retained_png)];assert original.shape==full.shape==retained.shape
    mask=np.zeros(original.shape[:2],dtype=bool)
    positions=lambda info:{row['cell']:[char for run in row['runs'] for char in run['chars']] for row in info['actual_text_positions']}
    a,b=positions(before_info),positions(all_info)
    boxes={}
    for key in rejected:
        chars=a[key]+b[key];box=[max(0,math.floor(min(c['x'] for c in chars))-margin),max(0,math.floor(min(c['y'] for c in chars))-margin),min(original.shape[1],math.ceil(max(c['x']+c['width'] for c in chars))+margin),min(original.shape[0],math.ceil(max(c['y']+c['height'] for c in chars))+margin)];boxes[key]=box;mask[box[1]:box[3],box[0]:box[2]]=True
    expected=full.copy();expected[mask]=original[mask];mismatch=int(np.any(expected!=retained,axis=2).sum())
    return {'ok':mismatch==0,'whole_canvas_pixel_mismatches':mismatch,'exact_original_pixels_for_reverted_objects':mismatch==0,'all_previously_proven_clip_pixels_elsewhere_unchanged':mismatch==0,'rejected_object_boxes':boxes}
