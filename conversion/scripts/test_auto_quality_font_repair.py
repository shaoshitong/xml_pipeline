import json,xml.etree.ElementTree as E
from auto_quality_font_repair import merge_fonts,check_faces,preserve_named_styles
def require_rejection(fn):
 try:fn();raise RuntimeError('Invalid font proof accepted')
 except AssertionError:pass
xml='<mxfile><diagram><mxGraphModel extFonts="New^data:font/ttf;base64,NEW"><root><mxCell id="x" value="same"/></root></mxGraphModel></diagram></mxfile>'
r=E.fromstring(merge_fonts(xml,'Original^data:font/ttf;base64,OLD'));ext=r.find('.//mxGraphModel').get('extFonts');assert 'Original^' in ext and 'New^' in ext;assert r.find('.//mxCell').get('value')=='same'
require_rejection(lambda:merge_fonts(xml,'New^different-payload'))
before=[{'cell':'a','actual_fonts':[{'postScriptName':'A','glyphCount':7,'isCustomFont':False}]}];after={'actual_platform_font_usage':[{'cell':'a','fonts':[{'postScriptName':'A','glyphCount':7,'isCustomFont':True}]}]};check_faces(before,after,{'a'})
for field,value in [('isCustomFont',False),('glyphCount',6),('postScriptName','B')]:
 bad=json.loads(json.dumps(after));bad['actual_platform_font_usage'][0]['fonts'][0][field]=value;require_rejection(lambda:check_faces(before,bad,{'a'}))
before_xml='<mxfile><diagram><mxGraphModel><root><mxCell id="a" style="text;html=1;fontFamily=Arial;rounded;strokeColor=none;"/></root></mxGraphModel></diagram></mxfile>'
after_xml=before_xml.replace('text;','').replace('rounded;','').replace('fontFamily=Arial','fontFamily=Embedded;fontSource=data')
fixed=preserve_named_styles(before_xml,after_xml,{'a'});assert E.fromstring(fixed).find('.//mxCell').get('style')=='text;html=1;rounded;strokeColor=none;fontFamily=Embedded;fontSource=data;'
require_rejection(lambda:preserve_named_styles(before_xml,after_xml.replace('strokeColor=none','strokeColor=red'),{'a'}))
print(json.dumps({'ok':True,'fixtures':8,'original_unused_font_preserved':True,'glyph_face_fallback_negatives_rejected':True,'named_styles_and_paint_order_preserved':True}))
