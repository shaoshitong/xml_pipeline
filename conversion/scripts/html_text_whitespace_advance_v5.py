"""Prototype recover measured source ASCII-space advances without changing text.

A collapsed logical single space can represent multiple source CSS spaces. Its
Range width difference alone determines word-spacing. All text nodes are wrapped
so the physical-font collector does not double-count a containing text parent.
This module never publishes, calls a model, or alters any database/queue.
"""
import copy
import html
from html.parser import HTMLParser
import re
import statistics
import xml.etree.ElementTree as E
from html_actual_text_alignment import analyze,_plain,_canonical_text,sha,SIZE_TOLERANCE
from html_actual_text_registration import _signature


def plan(dom,info,xml,offset=(0,0)):
    analysis=analyze(dom,info,xml,offset);objects={str(obj['id']+1):obj for obj in dom['objects'] if obj['type']=='text'};rows={row['cell']:row for row in info['actual_text_positions']};cells={cell.get('id'):cell for cell in E.fromstring(xml).iter('mxCell')};plans=[];unsupported=[]
    for diagnosis in analysis['objects']:
        key=diagnosis['cell'];obj=objects[key];source=obj.get('actualSourceGlyphs',[]);native=[char for run in rows.get(key,{}).get('runs',[]) for char in run['chars']]
        targets=[]
        if len(source)!=len(native) or [_canonical_text(c['text']) for c in source]!=[_canonical_text(c['text']) for c in native]:continue
        logical_offset=0
        for index,(s,n) in enumerate(zip(source,native)):
            if s['text']==' ' and re.fullmatch(' {2,}',s.get('raw','')) and s['width']-n['width']>SIZE_TOLERANCE:
                targets.append({'grapheme_index':index,'logical_offset':logical_offset,'extra_advance':s['width']-n['width'],'source_raw_spaces':s['raw'],'source_space_width':s['width'],'native_space_width':n['width']})
            logical_offset+=len(n['text'])
        if not targets:continue
        try:
            assert _plain(cells[key].get('value',''))==obj['text'],'Source/native logical text differs'
            assert diagnosis.get('source_faces')==diagnosis.get('native_faces') and diagnosis.get('source_faces'),'Source/native physical face set differs or is unresolved'
            assert len(diagnosis.get('native_font_sizes',[]))==1 and abs(diagnosis['native_font_sizes'][0]-diagnosis['source_font_size'])<=.001,'Source/native CSS size differs'
            assert not obj.get('sourceClip',{}).get('partial') and 'clip-path' not in cells[key].get('value',''),'Changing a clip reference-box width needs a separate fixed-clip adapter'
            assert 'word-spacing' not in cells[key].get('value','').lower(),'Existing per-run word-spacing needs an additive computed-CSS adapter'
            selected={row['grapheme_index']:row for row in targets};cumulative=0;residuals=[]
            for index,(s,n) in enumerate(zip(source,native)):
                expected_width_delta=selected.get(index,{}).get('extra_advance',0)
                assert abs(s['width']-n['width']-expected_width_delta)<=SIZE_TOLERANCE,'A non-whitespace source glyph has a different advance'
                residuals.append(s['x']+offset[0]-n['x']-cumulative)
                cumulative+=expected_width_delta
            median=statistics.median(residuals);spread=max(abs(value-median) for value in residuals)
            assert spread<=SIZE_TOLERANCE,'Whitespace advances do not explain every following glyph x residual'
            plans.append({'cell':key,'targets':targets,'source_physical_faces':diagnosis['source_faces'],'source_font_size':diagnosis['source_font_size'],'source_x_residual_after_only_space_advances':median,'maximum_horizontal_residual_spread':spread,'source_baseline_or_nonspace_height_not_changed':True})
        except AssertionError as error:unsupported.append({'cell':key,'reason':str(error)})
    return {'objects':plans,'unsupported':unsupported,'eligible_count':len(plans),'parameters_from_actual_source_space_ranges_only':True}


class _Wrap(HTMLParser):
    def __init__(self,value,targets):
        super().__init__(convert_charrefs=False);self.value=value;self.targets=targets;self.tokens=[];self.pending='';self.logical_offset=0;self.line_offsets=[0]
        for index,char in enumerate(value):
            if char=='\n':self.line_offsets.append(index+1)
    def raw_tag(self):
        line,column=self.getpos();start=self.line_offsets[line-1]+column;return self.value[start:self.value.index('>',start)+1]
    def flush(self):
        text=self.pending;self.pending='';start=self.logical_offset;cursor=0
        for index,char in enumerate(text):
            target=self.targets.get(start+index)
            if target is None:continue
            assert char==' ','The selected logical whitespace codepoint changed'
            if index>cursor:self.tokens.append('<span data-img2code-space-layout="v5">'+html.escape(text[cursor:index],quote=False)+'</span>')
            self.tokens.append('<span data-img2code-space-layout="v5" style="word-spacing:'+format(target['extra_advance'],'.10g')+'px;"> </span>');cursor=index+1
        if cursor<len(text):self.tokens.append('<span data-img2code-space-layout="v5">'+html.escape(text[cursor:],quote=False)+'</span>')
        self.logical_offset+=len(text)
    def handle_data(self,data):self.pending+=data
    def handle_entityref(self,name):self.pending+=html.unescape('&'+name+';')
    def handle_charref(self,name):self.pending+=html.unescape('&#'+name+';')
    def handle_starttag(self,tag,attrs):self.flush();self.tokens.append(self.get_starttag_text())
    def handle_startendtag(self,tag,attrs):self.flush();self.tokens.append(self.get_starttag_text())
    def handle_endtag(self,tag):self.flush();self.tokens.append(self.raw_tag())
    def handle_comment(self,data):self.flush();self.tokens.append('<!--'+data+'-->')
    def result(self):self.flush();return ''.join(self.tokens)


def propose(xml,plan,cells=None):
    root=E.fromstring(xml);lookup={cell.get('id'):cell for cell in root.iter('mxCell')};changes=[]
    for row in plan['objects']:
        if cells is not None and row['cell'] not in cells:continue
        cell=lookup[row['cell']];before=cell.get('value','');parser=_Wrap(before,{target['logical_offset']:target for target in row['targets']});parser.feed(before);parser.close();value=parser.result();assert _plain(value)==_plain(before),'Whitespace layout changed logical text'
        cell.set('value',value);changes.append({**copy.deepcopy(row),'before_value':before,'after_value':value})
    candidate=E.tostring(root,encoding='unicode');restored=E.fromstring(candidate);changes_by_id={row['cell']:row for row in changes}
    for cell in restored.iter('mxCell'):
        if cell.get('id') in changes_by_id:cell.set('value',changes_by_id[cell.get('id')]['before_value'])
    assert E.canonicalize(E.tostring(restored,encoding='unicode'))==E.canonicalize(xml),'A graph/geometry/font-style/asset changed'
    return candidate,{'version':5,'input_code_sha256':sha(xml.encode()),'output_code_sha256':sha(candidate.encode()),'changes':changes,'logical_text_and_all_graph_geometry_preserved':True,'parameters_from_actual_space_range_advance_only':True,'accepted':False}


def actual_advance_checks(proof,before,after):
    positions=lambda info:{row['cell']:[char for run in row['runs'] for char in run['chars']] for row in info['actual_text_positions']}
    a,b=positions(before),positions(after);old_fonts={row['cell']:_signature(row['fonts']) for row in before['actual_platform_font_usage']};new_fonts={row['cell']:_signature(row['fonts']) for row in after['actual_platform_font_usage']};results=[]
    for change in proof['changes']:
        key=change['cell'];sequence=key in a and key in b and [char['text'] for char in a[key]]==[char['text'] for char in b[key]];maximum=float('inf');bad=[]
        if sequence:
            targets={row['grapheme_index']:row for row in change['targets']};cumulative=0;maximum=0
            for index,(old,new) in enumerate(zip(a[key],b[key])):
                advance=targets.get(index,{}).get('extra_advance',0);errors={'x':abs(new['x']-old['x']-cumulative),'y':abs(new['y']-old['y']),'height':abs(new['height']-old['height']),'width':abs(new['width']-old['width']-advance)};maximum=max(maximum,*errors.values());cumulative+=advance
                if max(errors.values())>SIZE_TOLERANCE:bad.append({'grapheme_index':index,'text':old['text'],'errors':errors})
        same_fonts=bool(old_fonts.get(key)) and old_fonts.get(key)==new_fonts.get(key)
        results.append({'cell':key,'ok':sequence and maximum<=SIZE_TOLERANCE and same_fonts,'maximum_actual_advance_or_unchanged_geometry_error':maximum,'logical_sequence_unchanged':sequence,'physical_faces_and_glyph_counts_unchanged':same_fonts,'bad_graphemes':bad[:12],'reason':None if sequence and maximum<=SIZE_TOLERANCE and same_fonts else 'CSS_text_run_boundary_changed_kerning_or_other_glyph_geometry_or_font_counts'})
    return results


def verify(before_xml,after_xml,proof,dom,before,after,offset=(0,0)):
    plans=plan(dom,before,before_xml,offset);expected,replayed=propose(before_xml,plans,{row['cell'] for row in proof['changes']});assert E.canonicalize(expected)==E.canonicalize(after_xml) and proof['changes']==replayed['changes'],'Unproved whitespace/graph delta'
    checks=actual_advance_checks(proof,before,after);assert all(row['ok'] for row in checks),'Current actual glyph changes exceed the measured whitespace-only advances'
    verified=[{'cell':row['cell'],'maximum_actual_advance_or_unchanged_geometry_error':row['maximum_actual_advance_or_unchanged_geometry_error'],'actual_nonspace_width_height_and_all_y_unchanged':True} for row in checks]
    changed={row['cell'] for row in proof['changes']}
    from html_text_layout_registration_v5 import require_same_actual_positions
    require_same_actual_positions({'actual_text_positions':[row for row in before['actual_text_positions'] if row['cell'] not in changed]},{'actual_text_positions':[row for row in after['actual_text_positions'] if row['cell'] not in changed]})
    old_fonts={row['cell']:_signature(row['fonts']) for row in before['actual_platform_font_usage']};new_fonts={row['cell']:_signature(row['fonts']) for row in after['actual_platform_font_usage']};assert old_fonts==new_fonts,'An original actual physical face/glyph count changed';assert all(font.get('isCustomFont') for row in after['actual_platform_font_usage'] for font in row['fonts'] if font.get('glyphCount',0)),'Unembedded font'
    return {'ok':True,'objects':verified,'all_original_physical_faces_and_glyph_counts_preserved':True,'all_geometry_and_logical_text_unchanged':True,'scope':'Only the measured extra width of normalized ASCII spaces and the corresponding following glyph x advances; baseline differences remain explicit and original-image gates still apply.'}
