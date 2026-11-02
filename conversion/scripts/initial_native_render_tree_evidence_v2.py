"""Complete live-render observations for reviewing a future content contract.

This module is not a release gate: it captures every live graph node and full
computed styles, and reports raw differences. A translation normalizer must be
proved separately; unknown paint/tree features are explicitly unsupported.
"""
import collections,hashlib,json
sha=lambda raw:hashlib.sha256(raw).hexdigest()
canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
EXTRACTOR=r"""()=>{
 const graph=document.getElementById('graph'),g=window.evalViewer.graph,resources=new Set(),errors=[];
 const css=style=>{const value={};for(const key of style){value[key]=style.getPropertyValue(key);for(const match of value[key].matchAll(/url\((?:['"])?([^)'"\s]+)(?:['"])?\)/g))resources.add(match[1]);}return value;};
 const matrix=value=>value?{a:value.a,b:value.b,c:value.c,d:value.d,e:value.e,f:value.f,is2D:value.is2D}:null;
 const rect=value=>value?{x:value.x,y:value.y,width:value.width,height:value.height}:null;
 const walk=(node,path)=>{
  if(node.nodeType===Node.TEXT_NODE)return {path,nodeType:3,text:node.nodeValue};
  if(node.nodeType===Node.COMMENT_NODE)return {path,nodeType:8,text:node.nodeValue};
  if(node.nodeType!==Node.ELEMENT_NODE)return {path,nodeType:node.nodeType,unsupportedNode:true};
  const attributes=[...node.attributes].map(a=>({namespace:a.namespaceURI,name:a.name,value:a.value})).sort((a,b)=>(a.namespace||'').localeCompare(b.namespace||'')||a.name.localeCompare(b.name));
  for(const a of attributes)if(['href','xlink:href','src'].includes(a.name))resources.add(a.value);
  const computed=css(getComputedStyle(node)),pseudo={};
  for(const name of ['::before','::after']){const style=getComputedStyle(node,name);pseudo[name]={content:style.content};if(!['none','normal',''].includes(style.content))pseudo[name].computed=css(style);}
  let bbox=null,bboxError=null,ctm=null,screenCTM=null;
  try{if(node.getBBox)bbox=rect(node.getBBox());}catch(e){bboxError=String(e);}
  try{if(node.getCTM)ctm=matrix(node.getCTM());if(node.getScreenCTM)screenCTM=matrix(node.getScreenCTM());}catch(e){errors.push({path,kind:'matrix',error:String(e)});}
  return {path,nodeType:1,namespace:node.namespaceURI,tag:node.localName,attributes,computed,pseudo,bbox,bboxError,ctm,screenCTM,rect:rect(node.getBoundingClientRect()),children:[...node.childNodes].map((child,i)=>walk(child,path+'/'+i))};
 };
 const rules=[];for(const sheet of document.styleSheets){try{for(const rule of sheet.cssRules)if(rule.type===CSSRule.FONT_FACE_RULE)rules.push(rule.cssText);}catch(e){errors.push({kind:'stylesheet-access',href:sheet.href,error:String(e)});}}
 const snapshot={schema:'actual_graph_complete_live_dom_v2',context:{viewport:[innerWidth,innerHeight],devicePixelRatio,graphRect:rect(graph.getBoundingClientRect()),viewScale:g.view.scale,viewTranslate:[g.view.translate.x,g.view.translate.y],documentFontsStatus:document.fonts.status},tree:walk(graph,'0'),fontFaceRules:rules,fontFaces:[...document.fonts].map(f=>({family:f.family,style:f.style,weight:f.weight,stretch:f.stretch,unicodeRange:f.unicodeRange,featureSettings:f.featureSettings,variationSettings:f.variationSettings,display:f.display,status:f.status})),resources:[...resources].sort(),errors};return snapshot;
}"""

KNOWN_SVG={'svg','g','defs','path','rect','circle','ellipse','line','polyline','polygon','text','tspan','foreignObject','switch','clipPath','marker','use','image','title','desc','linearGradient','radialGradient','stop','symbol','style'}
KNOWN_HTML={'div','span','p','br','b','i','u','s','sub','sup'}
SVG='http://www.w3.org/2000/svg';HTML='http://www.w3.org/1999/xhtml'
def flatten(snapshot):
    result={}
    def walk(node):
        result[node['path']]=node
        for child in node.get('children',[]):walk(child)
    walk(snapshot['tree']);return result

def unsupported(snapshot):
    failures=list(snapshot.get('errors',[]))
    for path,node in flatten(snapshot).items():
        if node['nodeType'] not in [1,3,8]:failures.append({'path':path,'reason':'unknown_node_type'});continue
        if node['nodeType']!=1:continue
        allowed=node['namespace']==SVG and node['tag'] in KNOWN_SVG or node['namespace']==HTML and node['tag'] in KNOWN_HTML
        if not allowed:failures.append({'path':path,'reason':'unknown_node','namespace':node['namespace'],'tag':node['tag']})
        for name,value in node.get('pseudo',{}).items():
            if value.get('content') not in ['none','normal','']:failures.append({'path':path,'reason':'uninterpreted_pseudo_paint','pseudo':name})
        style=node.get('computed',{})
        for key in ['filter','backdrop-filter','mask-image','mix-blend-mode','background-image','box-shadow','text-shadow','animation-name']:
            value=style.get(key)
            if value not in [None,'none','normal']:failures.append({'path':path,'reason':'paint_effect_requires_complete_interpreter','property':key,'value':value})
        for key in ['ctm','screenCTM']:
            matrix=node.get(key)
            if matrix and (matrix.get('is2D') is False or any(matrix.get(k)!=v for k,v in [('a',1),('b',0),('c',0),('d',1)])):failures.append({'path':path,'reason':'nontranslation_matrix_requires_interpreter','kind':key,'matrix':matrix})
    for resource in snapshot.get('resources',[]):
        if resource and not resource.startswith(('data:','#','about:blank#')):failures.append({'reason':'unresolved_external_or_contextual_resource','resource_sha256':sha(resource.encode())})
    return failures

def summarize_diff(before,after,translation):
    left=flatten(before);right=flatten(after);tags_before=collections.Counter((node.get('namespace'),node.get('tag')) for node in left.values() if node['nodeType']==1);tags_after=collections.Counter((node.get('namespace'),node.get('tag')) for node in right.values() if node['nodeType']==1);attributes=collections.Counter();styles=collections.Counter();field_changes=collections.Counter();examples=[];text_equal=True
    for path in sorted(set(left)|set(right)):
        a=left.get(path);b=right.get(path)
        if not a or not b:field_changes['tree-node-missing']+=1;continue
        if (a.get('nodeType'),a.get('namespace'),a.get('tag'))!=(b.get('nodeType'),b.get('namespace'),b.get('tag')):field_changes['node-type-or-tag']+=1;continue
        if a.get('text')!=b.get('text'):text_equal=False;field_changes['text']+=1
        aa={row['name']:row['value'] for row in a.get('attributes',[])};bb={row['name']:row['value'] for row in b.get('attributes',[])}
        for name in sorted(set(aa)|set(bb)):
            if aa.get(name)==bb.get(name):continue
            attributes[name]+=1
            if len(examples)<30:examples.append({'path':path,'tag':a.get('tag'),'attribute':name,'before_sha256':sha(str(aa.get(name)).encode()),'after_sha256':sha(str(bb.get(name)).encode()),'before_numeric_or_short':aa.get(name) if name in ['x','y','width','height','transform','clip-path'] and len(str(aa.get(name)))<100 else None,'after_numeric_or_short':bb.get(name) if name in ['x','y','width','height','transform','clip-path'] and len(str(bb.get(name)))<100 else None})
        sa=a.get('computed',{});sb=b.get('computed',{})
        for name in sorted(set(sa)|set(sb)):
            if sa.get(name)!=sb.get(name):styles[name]+=1
        for name in ['bbox','ctm','screenCTM','rect','pseudo']:
            if a.get(name)!=b.get(name):field_changes[name]+=1
    issues_before=unsupported(before);issues_after=unsupported(after)
    return {'schema':'actual_render_tree_diff_evidence_only_v2','translation':translation,'node_count_before':len(left),'node_count_after':len(right),'tag_counts_before':[{'namespace':key[0],'tag':key[1],'count':count} for key,count in sorted(tags_before.items())],'tag_counts_after':[{'namespace':key[0],'tag':key[1],'count':count} for key,count in sorted(tags_after.items())],'same_node_taxonomy':tags_before==tags_after,'all_text_nodes_exact':text_equal,'attribute_difference_counts':dict(attributes),'computed_style_difference_counts':dict(styles),'other_field_difference_counts':dict(field_changes),'attribute_difference_examples':examples,'font_face_rules_exact':before.get('fontFaceRules')==after.get('fontFaceRules'),'font_face_statuses_exact':before.get('fontFaces')==after.get('fontFaces'),'resource_values_exact':before.get('resources')==after.get('resources'),'context_before':before['context'],'context_after':after['context'],'unsupported_before':issues_before,'unsupported_after':issues_after,'raw_complete_snapshots_exact':canonical(before)==canonical(after),'full_translation_equivalence_certified':False,'certification_refusal':'No complete translation-covariant path/paint/clip/marker/CSS interpreter is implemented by this evidence collector. Unchanged bbox or surface metadata cannot authorize equivalence.','accepted':False}
