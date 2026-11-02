"""Exact official PlantUML filter operators -> official native CSS shadow.

Pixel rounding differs between SVG primitive and CSS-filter evaluation; this is
an independent source-effect rule, never a pixel-exact alias. Original full
PNG, complete-source-label visual and source-domain thresholds are unchanged.
"""
import json,math,re,xml.etree.ElementTree as E
POLICY='official_PlantUML_black_gaussian2_alpha0_4_offset4_native_source_effect_v1'
PARAMS=dict(sigma=2.,alpha=.4,dx=4.,dy=4.,color='#000000')
KEYS=dict(shadow='1',shadowColor='#000000',shadowOpacity='40',shadowOffsetX='4',shadowOffsetY='4',shadowBlur='2')
def require(x,r):
 if not x:raise ValueError(r)
def specs(svg):
 root=E.fromstring(svg);out={};local=lambda e:e.tag.rsplit('}',1)[-1]
 for f in root.iter():
  if local(f)!='filter':continue
  ident=f.get('id');require(ident and ident not in out,'source_filter_identity_missing_or_duplicate')
  ops=list(f);typ=[local(x)for x in ops]
  good=typ==['feGaussianBlur','feColorMatrix','feOffset','feBlend']
  try:
   good=good and f.get('filterUnits','objectBoundingBox')=='objectBoundingBox'and f.get('primitiveUnits','userSpaceOnUse')=='userSpaceOnUse'and float(f.get('x'))==-1 and float(f.get('y'))==-1 and f.get('width')=='300%'and f.get('height')=='300%'
   a,b,c,d=ops
   good=good and a.get('in','SourceGraphic')=='SourceGraphic'and float(a.get('stdDeviation'))==2 and a.get('result')=='blurOut'
   good=good and b.get('in')=='blurOut'and b.get('result')=='blurOut2'and b.get('type')=='matrix'and list(map(float,b.get('values').split()))==[0]*18+[.4,0]
   good=good and c.get('in')=='blurOut2'and c.get('result')=='blurOut3'and float(c.get('dx'))==4 and float(c.get('dy'))==4
   good=good and d.get('in')=='SourceGraphic'and d.get('in2')=='blurOut3'and d.get('mode')=='normal'
   allowed=[{'in','stdDeviation','result'},{'in','result','type','values'},{'in','result','dx','dy'},{'in','in2','mode'}]
   good=good and all(set(o.attrib)<=keys for o,keys in zip(ops,allowed))and set(f.attrib)<={'id','x','y','width','height','filterUnits','primitiveUnits','color-interpolation-filters'}and f.get('color-interpolation-filters','linearRGB')=='linearRGB'
  except (ValueError,TypeError,AttributeError):good=False
  out[ident]={'supported':bool(good),'params':PARAMS,'operators':typ,'definition':{'id':ident,'attrs':dict(f.attrib),'children':[{'tag':local(x),'attrs':dict(x.attrib)}for x in ops]},'source_definition':E.tostring(f,encoding='unicode'),'policy':POLICY}
 return out
OBSERVE=r"""specs=>{const root=document.querySelector('svg'),map=new WeakMap,rows=[];const all=[...root.querySelectorAll('path,rect,circle,ellipse,line,polygon,polyline,text')].filter(e=>!e.closest('defs,marker,symbol,clipPath,mask'));for(let i=0;i<all.length;i++){const e=all[i],c=getComputedStyle(e);if(c.filter==='none')continue;const raw=e.getAttribute('filter')||e.style.filter||'',m=raw.match(/^url\(["']?#([^"')]+)["']?\)$/);if(!m||!specs[m[1]]?.supported)throw Error('typed_original_source_filter_operator_profile_pending');if(!['path','rect','circle','ellipse','polygon','polyline'].includes(e.localName))throw Error('typed_source_shadow_on_non_native_primary_shape_pending');if(+c.opacity!==1)throw Error('typed_post_filter_element_opacity_pending');for(let p=e.parentElement;p;p=p.parentElement){const pc=getComputedStyle(p);if(+pc.opacity!==1)throw Error('typed_post_filter_ancestor_opacity_pending');if(p!==root&&pc.filter!=='none')throw Error('typed_nested_source_filter_pending');if(p===root)break;}const b=e.getBBox(),ctm=e.getScreenCTM();if(!(b.width>=16&&b.height>=16)||Math.abs(ctm.a-1)>1e-8||Math.abs(ctm.b)>1e-8||Math.abs(ctm.c)>1e-8||Math.abs(ctm.d-1)>1e-8)throw Error('typed_source_shadow_region_or_scaled_kernel_pending');const row={...specs[m[1]],filter_id:m[1],source_element_ordinal:i,source_bbox:[b.x,b.y,b.width,b.height],source_computed_filter:c.filter,actual_source_primary_primitive:true};map.set(e,row);rows.push(row);}window.__plantumlNativeShadowMapV1=map;return{policy:'official_PlantUML_black_gaussian2_alpha0_4_offset4_native_source_effect_v1',actual_filtered_primitives:rows,unexpanded_or_unknown_filters:0,not_pixel_exact_alias:true};}"""
def annotate(page,svg):return page.evaluate(OBSERVE,specs(svg))
def native_style(style,source_shadow):
 expected=KEYS if source_shadow else{'shadow':'0'}
 if source_shadow:
  require(source_shadow.get('supported')is True and source_shadow.get('params')==PARAMS,'source_shadow_operator_proof_missing')
  require(all(str(style.get(k))==v for k,v in KEYS.items()),'native_source_shadow_parameters_changed')
 else:require(style.get('shadow','0')in('0',''),'undeclared_native_shadow')
 return True
