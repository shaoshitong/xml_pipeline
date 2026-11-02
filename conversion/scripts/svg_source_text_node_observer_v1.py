"""Observe SVG Text backends without inserting tspan layout boxes.

Only neutral parent identity attributes are added to the live observation DOM.
Every original Text node, parent/child membership, string and visible pixel is
preserved. Physical font queries target one materialized original Text backend.
"""
import hashlib,io
from PIL import Image
POLICY='original_svg_text_node_materialized_backend_no_layout_wrapper_v1'
MARK=r'''()=>{const painted=n=>{const p=n.parentElement;if(!p||p.closest('defs,marker,symbol,pattern,clipPath,mask')||getComputedStyle(p).visibility!=='visible')return false;for(let a=p;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||+c.opacity===0)return false;}return true;};let serial=0,nodes=0;const marked=new Set();for(const text of document.querySelectorAll('svg text')){const walker=document.createTreeWalker(text,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim()||!painted(n))continue;const r=document.createRange();r.selectNodeContents(n);const b=r.getBoundingClientRect();if(!b.width||!b.height)continue;const parent=n.parentElement;if(!marked.has(parent)){if(parent.hasAttribute('data-compiler-scene-run-v2'))throw Error('source_reserved_text_observer_identity_attribute');parent.setAttribute('data-compiler-scene-run-v2',String(serial++));marked.add(parent);}nodes++;}}return {parents:serial,originalTextNodes:nodes,newLayoutElements:0};}'''
def _pixels(b):
 with Image.open(io.BytesIO(b))as im:return im.size,im.convert('RGBA').tobytes()
def mark(page,screenshot):
 before=screenshot(page);proof=page.evaluate(MARK);after=screenshot(page)
 if _pixels(before)!=_pixels(after):raise ValueError('source_text_parent_identity_changed_actual_pixels')
 return {'policy':POLICY,**proof,'source_actual_pixels_exactly_preserved':True,'source_before_png_sha256':hashlib.sha256(before).hexdigest(),'source_after_png_sha256':hashlib.sha256(after).hexdigest()}
def physical_fonts(session,parent,index,text):
 from compiler_native_text_node_cdp_v2 import physical_fonts as exact_backend
 return exact_backend(session,parent,index,text)
