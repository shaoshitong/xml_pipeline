"""Deterministic proposals for omitted wrapped words and actual browser paint order.

No jobs or canonical files are mutated. Call propose(record, xml), then the common
fresh native rendering/font/resource/image gate, before publishing the revision.
"""
import argparse
import copy
import hashlib
import html
import io
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as E
import auto_quality_source_vector_v2 as q

sha=lambda b:hashlib.sha256(b).hexdigest()


def _font_key(obj):
    return (obj.get('fontFamilyRaw'),obj.get('bold'),obj.get('italic'),obj.get('underline'))


def _clip_added_text(xml, dom, added_ids, width, height, work):
    objects=[obj for obj in dom['objects'] if str(obj['id']+1) in added_ids and obj.get('sourceClip',{}).get('partial')]
    if not objects:
        return xml, {'required':False,'changes':[]}
    from native_worker import native
    from native_text_clip import apply_clips,verify_graph,verify_positions,pixel_clip_proof
    from native_clip_reference_box import correct_reference_boxes
    renderer=q.W/'rendering_clipbox_strict/remote_render.py'
    runtime=q.R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
    def render(value,name):
        result=native.native_job(value,width,height,150,renderer,8192,runtime)
        assert result['ok'], 'Native source clip rendering failed'
        assert result['native_render']['selected_image']=='declared_first_page', 'Unclipped proposal needs a same-view padded source clip proof'
        (work/(name+'.png')).write_bytes(result['png'])
        (work/(name+'_render.json')).write_text(json.dumps(result['native_render'],indent=2)+'\n')
        return result
    before=render(xml,'unclipped_added_text')
    new,details=apply_clips(xml,{'objects':objects},before['native_render']['actual_text_positions'],width,height)
    verify_graph(xml,new,details)
    after=render(new,'clipped_added_text_probe')
    new,details=correct_reference_boxes(new,details,after['native_render']['actual_clip_boxes'])
    if details['reference_box_adjusted_cells']:
        verify_graph(xml,new,details)
        after=render(new,'clipped_added_text')
    verify_positions(before['native_render']['actual_text_positions'],after['native_render']['actual_text_positions'])
    usage=lambda result:{row['cell']:row['fonts'] for row in result['native_render']['actual_platform_font_usage']}
    assert usage(before)==usage(after), 'Clip changed physical glyph usage'
    assert all(f['isCustomFont'] for fonts in usage(after).values() for f in fonts if f['glyphCount']), 'New text used an unembedded fallback'
    background=E.fromstring(xml)
    clipped_ids={change['cell'] for change in details['changes']}
    for cell in background.iter('mxCell'):
        if cell.get('id') in clipped_ids:cell.set('value','')
    bg=render(E.tostring(background,encoding='unicode'),'added_text_background')
    pixel=pixel_clip_proof(before['png'],after['png'],bg['png'],details)
    assert pixel['ok'], 'Source rectangular clip pixels differ from expected mask'
    result={'required':True,'details':details,'source_clip_pixel_proof':pixel,'all_character_geometry_and_actual_fonts_unchanged':True,'actual_font_usage':usage(after)}
    (work/'added_text_clip_proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return new,result


def propose(record, xml, work=None):
    from PIL import Image
    assert record['source_format']=='html' and record['category']=='poster', 'HTML poster profile only'
    code=q._identity(record,xml)
    work=Path(work) if work else q.W/'html_source_repair_v2_smoke'/record['id']/record['code_sha256']
    work.mkdir(parents=True,exist_ok=True)
    width,height=Image.open(io.BytesIO(q._read_clean(record['original_reference'],record['source_image_sha256']))).size
    dom,served=q._capture(record,code,width,height,'html')
    assert not [i for i in dom['unsupported'] if i.get('reason')!='css_stacking_order'], 'Unsupported source features require a different repair profile'
    root=E.fromstring(xml);cell_root=root.find('.//mxGraphModel/root')
    assert cell_root is not None, 'one uncompressed native graph required'
    cells={c.get('id'):c for c in cell_root.findall('mxCell')}
    originals={key:E.tostring(cell) for key,cell in cells.items()}
    source={str(obj['id']+1):obj for obj in dom['objects']}
    native_vertices={key for key,cell in cells.items() if cell.get('vertex')=='1'}
    expected=set(source)
    assert not native_vertices-expected, 'Extra native objects require independent source mapping'
    assert all(c.get('parent')=='1' for c in cells.values() if c.get('vertex')=='1'), 'Source paint sorting currently requires flat poster objects'
    assert not any(c.get('edge')=='1' for c in cells.values()), 'HTML diagram connectors require another profile'
    missing=expected-native_vertices
    assert all(source[key].get('qaWrappedFragment') for key in missing), 'Only verified omitted wrapped word fragments may be added'
    donor_objects=[(key,obj) for key,obj in source.items() if key in native_vertices and obj['type']=='text']
    additions=[]
    for key in sorted(missing,key=lambda k:(source[k]['qaPaintEvent'],source[k]['qaTextStart'])):
        obj=source[key]
        assert not obj.get('sourceClip',{}).get('unmodeled'), 'New source text uses unsupported clipping/transforms'
        donors=[(other_key,other) for other_key,other in donor_objects if _font_key(other)==_font_key(obj)]
        assert donors, 'No independently embedded source-style-matched font donor'
        donor_key,donor=min(donors,key=lambda pair:(abs(pair[1]['fontSize']-obj['fontSize']),abs(pair[1]['x']-obj['x'])+abs(pair[1]['y']-obj['y'])))
        donor_cell=cells[donor_key];style=q._style(donor_cell)
        assert style.get('shape')=='text' and style.get('fontFamily'), 'Missing editable embedded font donor'
        # No old per-character spans/clips are copied; retain the native physical
        # font stack and its existing embedded resources for this same source style.
        for name in ('clipPath','overflow','textOverflow'):
            style.pop(name,None)
        style.update(shape='text',html='1',align='left',verticalAlign='middle',spacing='0',whiteSpace='nowrap',overflow='visible',strokeColor='none',fillColor='none',fontSize=str(obj['fontSize']),fontColor=obj['color']['color'],opacity=str(obj['opacity']*obj['color'].get('opacity',1)*100))
        cell=E.Element('mxCell',{'id':key,'parent':'1','vertex':'1','value':html.escape(obj['text']),'style':';'.join(name+'='+str(value) for name,value in style.items())+';'})
        E.SubElement(cell,'mxGeometry',{'x':str(obj['x']),'y':str(obj['y']),'width':str(obj['w']),'height':str(obj['h']),'as':'geometry'})
        cell_root.append(cell);cells[key]=cell
        additions.append({'cell':key,'text':obj['text'],'source_word':obj['qaWordText'],'source_word_start':obj['qaWordStart'],'source_owner':obj['qaOwner'],'source_fragment':obj['qaFragmentIndex'],'font_donor_cell':donor_key,'font_family':style['fontFamily'],'source_bbox':[obj[k] for k in ('x','y','w','h')]})
    order=dom['_source_paint_order']
    source_order={str(obj['id']+1):(order[str(obj['id'])],obj.get('qaPaintEvent',i),obj.get('qaTextStart',0)) for i,obj in enumerate(dom['objects'])}
    objects=[c for c in cell_root.findall('mxCell') if c.get('vertex')=='1']
    before_order=[c.get('id') for c in objects]
    sorted_objects=sorted(objects,key=lambda c:source_order[c.get('id')])
    for cell in objects:cell_root.remove(cell)
    for cell in sorted_objects:cell_root.append(cell)
    proposed=E.tostring(root,encoding='unicode')
    proposed,clip_proof=_clip_added_text(proposed,dom,missing,width,height,work)
    root=E.fromstring(proposed);cell_root=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in cell_root.findall('mxCell')}
    # Every original cell (including native embedded font attributes, source
    # assets, geometry and text) is byte-identical under this same serializer.
    assert all(E.tostring(cells[key])==blob for key,blob in originals.items()), 'Existing object payload changed'
    assert {c.get('id') for c in cell_root.findall('mxCell')}-set(originals)==missing
    coverage=q._html_coverage(dom,proposed,served)
    assert coverage['ok'], json.dumps(coverage['errors'])[:2000]
    paint=q._html_paint_order(dom,proposed)
    assert paint['ok'],json.dumps(paint['errors'])[:2000]
    proof={'version':2,'input_code_sha256':record['code_sha256'],'output_code_sha256':sha(proposed.encode()),'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'fresh_source_dom_sha256':sha(json.dumps(dom,sort_keys=True).encode()),'all_existing_object_payloads_unchanged':True,'original_cell_count':len(originals),'new_editable_text_fragments':additions,'source_word_range_proofs':dom.get('qaWrappedWords',[]),'native_paint_order_before':before_order,'native_paint_order_after':[c.get('id') for c in sorted_objects],'paint_order_changed':before_order!=[c.get('id') for c in sorted_objects],'source_coverage':coverage,'actual_browser_paint_order':paint,'added_text_source_clips':clip_proof,'requires_common_fresh_render_font_resource_and_image_gates':True,'accepted':False}
    return proposed,proof


def main():
    parser=argparse.ArgumentParser();parser.add_argument('id');args=parser.parse_args()
    database=sqlite3.connect(f'file:{q.W}/jobs.sqlite?mode=ro',uri=True)
    state,raw=database.execute('select state,output_record from jobs where id=?',(args.id,)).fetchone()
    record=json.loads(raw);xml=q._read_clean(record['code_file'],record['code_sha256']).decode();work=q.W/'html_source_repair_v2_smoke'/args.id/record['code_sha256'];work.mkdir(parents=True,exist_ok=True)
    proposed,proof=propose(record,xml,work);(work/'candidate.drawio').write_text(proposed);(work/'proposal.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'id':args.id,'input_state':state,'directory':str(work.relative_to(q.R)),'input_code_sha256':record['code_sha256'],'output_code_sha256':proof['output_code_sha256'],'added_text_fragments':len(proof['new_editable_text_fragments']),'paint_order_changed':proof['paint_order_changed'],'source_coverage_ok':proof['source_coverage']['ok'],'canonical_changed':False,'accepted':False}))

if __name__=='__main__':main()
