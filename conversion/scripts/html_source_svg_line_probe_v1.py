"""Finite whole-line SVG text primitive. Source baseline/Unicode only, no fitting."""
import copy,html,re,xml.etree.ElementTree as E

def lower(xml,obj,source_baseline):
 root=E.fromstring(xml);cell=next(c for c in root.iter('mxCell')if c.get('id')==str(obj['id']+1));css=obj['actualSourceCss'];w,h=obj['w'],obj['h'];number=lambda n:format(float(n),'.12g')
 attrs={'x':'0','y':number(source_baseline-obj['y']),'font-size':number(css['fontSize']),'fill':obj['color']['color'],'xml:space':'preserve'}
 style='white-space:pre;font-kerning:'+css['fontKerning']+';font-feature-settings:'+css['fontFeatureSettings']+';font-variant-ligatures:'+css['fontVariantLigatures']+';letter-spacing:'+css['letterSpacing']+';text-rendering:'+css['textRendering']+';'
 text='<text '+' '.join(k+'="'+html.escape(str(v),quote=True)+'"'for k,v in attrs.items())+' style="'+style+'">'+html.escape(obj['text'])+'</text>'
 svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+number(w)+'" height="'+number(h)+'" viewBox="0 0 '+number(w)+' '+number(h)+'" style="overflow:visible;display:inline-block;">'+text+'</svg>'
 cell.set('value','<span data-img2code-source-svg-line="v1">'+svg+'</span>');return E.tostring(root,encoding='unicode')
