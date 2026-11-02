"""Conservative observed HTML/CSS template identity, without executing HTML.

Literal labels, numeric geometry, colors, asset names and font family names do
not establish a new family. DOM/paint order, CSS layout declarations, reference
sharing and repeated structure do. This cannot prove hidden generator identity.
"""
import hashlib
from html.parser import HTMLParser
import json
import re


class Tree(HTMLParser):
    VOID=set('area base br col embed hr img input link meta param source track wbr'.split())
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=['document',[],[]];self.stack=[self.root];self.ids={};self.classes={};self.tags={}
    def handle_starttag(self,tag,attrs):
        node=[tag,attrs,[]];self.stack[-1][2].append(node)
        for key,value in attrs:
            if key=='id' and value:self.ids.setdefault(value,'ID_'+str(len(self.ids)))
            if key=='class':
                for item in (value or '').split():self.classes.setdefault(item,'CLASS_'+str(len(self.classes)))
        self.tags[tag]=self.tags.get(tag,0)+1
        if tag not in self.VOID:self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i][0]==tag:
                self.stack=self.stack[:i];return
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in self.VOID:self.handle_endtag(tag)
    def handle_data(self,data):
        if not data.strip():return
        kind='css' if self.stack[-1][0]=='style' else 'text'
        children=self.stack[-1][2]
        if children and children[-1][0]==kind and len(children[-1])==2:children[-1][1]+=data
        else:children.append([kind,data])


def family(code):
    tree=Tree();tree.feed(code);tree.close()
    colors={};assets={};fonts={}
    number=re.compile(r'(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
    color=re.compile(r'#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?)\([^)]*\)|\b(?:black|white|red|green|blue|gray|grey|silver|yellow|orange|purple|pink|brown|cyan|magenta|navy|teal|maroon|lime|olive|aqua|fuchsia)\b',re.I)
    def scalar(value):
        value=color.sub(lambda m:colors.setdefault(m[0].lower(),'COLOR_'+str(len(colors))),value)
        return re.sub(r'\s+',' ',number.sub('N',value)).strip()
    def asset(value):return assets.setdefault(value,'ASSET_'+str(len(assets)))
    def css(value):
        value=re.sub(r'/\*.*?\*/','',value,flags=re.S)
        value=re.sub(r'url\(([^)]*)\)',lambda m:'url('+asset(m[1])+')',value)
        for name,alias in sorted(tree.ids.items(),key=lambda p:-len(p[0])):
            value=re.sub(r'#'+re.escape(name)+r'(?![\w-])','#'+alias,value)
        for name,alias in sorted(tree.classes.items(),key=lambda p:-len(p[0])):
            value=re.sub(r'\.'+re.escape(name)+r'(?![\w-])','.'+alias,value)
        value=re.sub(r'(font-family\s*:)\s*([^;}]+)',lambda m:m[1]+fonts.setdefault(m[2].strip().lower(),'FONT_'+str(len(fonts))),value,flags=re.I)
        value=scalar(value)
        return re.sub(r'\s*([{};:,>+~])\s*',r'\1',value)
    def walk(node):
        if len(node)==2:return ['css',css(node[1])] if node[0]=='css' else ['text','TEXT']
        tag,attrs,children=node;out=[]
        for key,value in sorted(attrs,key=lambda p:(p[0],p[1] or '')):
            value=value or ''
            if key=='id':value=tree.ids.get(value,'EMPTY_ID')
            elif key=='class':value=' '.join(tree.classes[item] for item in value.split())
            elif key=='style':value=css(value)
            elif key in ('src','href','srcset','poster','xlink:href'):value=asset(value)
            elif key in ('alt','title','aria-label','value','placeholder'):value='TEXT'
            else:value=scalar(value)
            out.append([key,value])
        return [tag,out,[walk(child) for child in children]]
    document=walk(tree.root)
    blob=json.dumps(document,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    return 'html_observed_DOM_CSS_template_v1:'+hashlib.sha256(blob).hexdigest(),{
        'tags':tree.tags,'DOM_elements':sum(tree.tags.values()),'asset_references':len(assets),
        'font_families':len(fonts),'source_only':True,'hidden_generator_independence_proven':False}
