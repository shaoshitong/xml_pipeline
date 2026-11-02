"""Preserve exact source paint while resolving image-bearing SVG use instances.

Only one-level local g/image targets with no text or active/effect content are
eligible. The browser's original use paint is the oracle, with zero RGBA error
before/after each materialization. This is source observation, not raster fitting.
"""
from pathlib import Path
import hashlib,io,json,uuid,xml.etree.ElementTree as ET
from PIL import Image

R=Path('/backup/shaoshitong/img2code_20261029')
POLICY='original_source_local_image_use_materialization_exact_RGBA_v1'
ATTR='data-compiler-source-image-definition-index-v1'
USE='data-compiler-source-image-use-index-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(value,why):
    if not value:raise ValueError(why)
def pixels(blob):
    with Image.open(io.BytesIO(blob))as im:return im.size,im.convert('RGBA').tobytes()
def save(p,blob):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb')as f:f.write(blob)
    return dict(file=str(p),sha256=sha(blob))

PREPARE=r'''() => {
 const root=document.querySelector('svg'),all=[...root.querySelectorAll('*')],images=[...root.querySelectorAll('image')],uses=[...root.querySelectorAll('use')];
 const forbidden=['data-compiler-source-image-definition-index-v1','data-compiler-source-image-use-index-v1'];
 for(const e of [root,...all])for(const a of forbidden)if(e.hasAttribute(a))throw Error('reserved_source_image_use_observer_attribute');
 const ids=new Map();for(const e of all)if(e.id){if(ids.has(e.id))throw Error('source_use_duplicate_original_ID');ids.set(e.id,e);}
 const list=[];
 for(const [index,use]of uses.entries()){
  const href=use.getAttribute('href')||use.getAttributeNS('http://www.w3.org/1999/xlink','href')||'',target=href.startsWith('#')?ids.get(href.slice(1)):null;
  if(!target||!['g','image'].includes(target.localName)||!(target.localName==='image'||target.querySelector('image')))continue;
  if(target.closest('symbol,marker,pattern,mask,clipPath'))continue;
  const subtree=[target,...target.querySelectorAll('*')];
  if(subtree.some(e=>['text','tspan','textPath','use','symbol','foreignObject','script','style','marker','filter','mask','clipPath','pattern','animate','animateTransform','set'].includes(e.localName)))continue;
  if(subtree.some(e=>{const c=getComputedStyle(e);return c.display==='none'||c.visibility!=='visible'||!(+c.opacity>0&&+c.opacity<=1)||(+c.opacity!==1&&e.localName!=='image')||c.filter!=='none'||c.clipPath!=='none'||c.maskImage!=='none'||c.mixBlendMode!=='normal'||c.isolation!=='auto';}))continue;
  const c=getComputedStyle(use);if(c.display==='none'||c.visibility!=='visible'||+c.opacity!==1||c.filter!=='none'||c.clipPath!=='none'||c.maskImage!=='none'||c.mixBlendMode!=='normal')continue;
  const defs=subtree.filter(e=>e.localName==='image').map(e=>images.indexOf(e));if(defs.some(x=>x<0))throw Error('source_use_image_definition_index_missing');
  list.push({index,source_document_index:all.indexOf(use),href,target_id:target.id,target_tag:target.localName,image_definition_indices:defs});
 }
 if(list.length)for(const [index,image]of images.entries())image.setAttribute('data-compiler-source-image-definition-index-v1',String(index));
 window.__sourceImageUseObservationV1={root,all,images,uses,ids,list,active:null};return list;
}'''
EXPAND=r'''index => {
 const s=window.__sourceImageUseObservationV1,use=s.uses[index],spec=s.list.find(r=>r.index===index);if(!spec||!use.isConnected)throw Error('source_image_use_identity_changed');
 const target=s.ids.get(spec.href.slice(1)),parent=use.parentElement,namespace='http://www.w3.org/2000/svg';
 const original=[target,...target.querySelectorAll('*')],clone=target.cloneNode(true),copies=[clone,...clone.querySelectorAll('*')];if(original.length!==copies.length)throw Error('source_image_use_clone_inventory_changed');
 for(let i=0;i<original.length;i++){
  copies[i].setAttribute('data-compiler-source-image-use-index-v1',String(index));
  if(original[i].localName==='image'){
  const definition=s.images.indexOf(original[i]);if(definition<0||copies[i].getAttribute('href')!==original[i].getAttribute('href')||copies[i].getAttributeNS('http://www.w3.org/1999/xlink','href')!==original[i].getAttributeNS('http://www.w3.org/1999/xlink','href'))throw Error('source_image_use_asset_identity_changed');
  copies[i].setAttribute('data-compiler-source-image-definition-index-v1',String(definition));copies[i].setAttribute('data-compiler-source-image-use-index-v1',String(index));
  }
 }
 const cs=getComputedStyle(use),g=document.createElementNS(namespace,'g');
 // SVG use x/y apply after its transform. Parent-relative matrix retains both.
 const matrix=parent.getScreenCTM().inverse().multiply(use.getScreenCTM()).translate(use.x.baseVal.value,use.y.baseVal.value);
 g.setAttribute('transform','matrix('+[matrix.a,matrix.b,matrix.c,matrix.d,matrix.e,matrix.f].join(',')+')');
 const inherited=['fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-dasharray','stroke-dashoffset','stroke-miterlimit','fill-rule','fill-opacity','stroke-opacity','color','visibility','paint-order','vector-effect'];
 for(const name of inherited)g.style.setProperty(name,cs.getPropertyValue(name),'important');
 g.appendChild(clone);parent.replaceChild(g,use);s.active={use,g,parent};
 return {spec,local_matrix:[matrix.a,matrix.b,matrix.c,matrix.d,matrix.e,matrix.f],source_asset_bytes_unchanged:true};
}'''
WAIT=r'''async()=>{await Promise.all([...document.querySelectorAll('svg image')].map(async e=>{const u=e.getAttribute('href')||e.getAttributeNS('http://www.w3.org/1999/xlink','href');if(!u?.startsWith('data:image/'))throw Error('source_use_external_image');const i=new Image();i.src=u;await i.decode();}));}'''

def materialize(page,source_bytes,screenshot,work=None):
    root=ET.fromstring(source_bytes);original_images=[e for e in root.iter()if e.tag.rsplit('}',1)[-1]=='image'];uses=[e for e in root.iter()if e.tag.rsplit('}',1)[-1]=='use']
    require(not any(ATTR in e.attrib or USE in e.attrib for e in root.iter()),'reserved_source_use_image_attribute')
    before=screenshot(page);base_pixels=pixels(before)
    specs=page.evaluate(PREPARE)
    if not specs:return dict(policy=POLICY,source_code_sha256=sha(source_bytes),materialized_invocations=0,all_original_source_pixels_exact=True,invocations=[])
    work=Path(work or R/'clean/svg_source_use_image_materialization_v1'/uuid.uuid4().hex).resolve()
    require(work.is_relative_to(R/'clean'),'source_image_use_proof_must_be_clean')
    work.mkdir(parents=True,exist_ok=False)
    report=dict(policy=POLICY,source_code_sha256=sha(source_bytes),original_image_definition_count=len(original_images),original_use_invocation_count=len(uses),
                before=save(work/'original_source.png',before),invocations=[],materialized_invocations=0,all_original_source_pixels_exact=False,
                models=0,interior_editability='original_image_asset_unit_only',no_new_combined_raster_assets=True)
    try:
        for spec in specs:
            i=spec['index'];require(0<=i<len(uses),'source_image_use_original_index_changed')
            href=uses[i].get('href')or uses[i].get('{http://www.w3.org/1999/xlink}href')or''
            require(href==spec['href'],'source_image_use_original_href_changed')
            for index in spec['image_definition_indices']:require(0<=index<len(original_images),'source_image_use_original_definition_changed')
            item=page.evaluate(EXPAND,i);page.evaluate(WAIT);after=screenshot(page)
            item['fresh_materialized_source']=save(work/('invocation_'+str(i)+'.png'),after)
            item['source_original_RGBA_exact']=pixels(after)==base_pixels
            report['invocations'].append(item)
            require(item['source_original_RGBA_exact'],'source_use_image_materialization_changed_original_pixels')
            report['materialized_invocations']+=1
        report['all_original_source_pixels_exact']=True
        report['after']=report['invocations'][-1]['fresh_materialized_source']
        report['proof_file']=str(work/'proof.json')
        save(work/'proof.json',(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
        return report
    except Exception as error:
        report['typed_failure']=str(error)
        save(work/'proof.json',(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
        raise
