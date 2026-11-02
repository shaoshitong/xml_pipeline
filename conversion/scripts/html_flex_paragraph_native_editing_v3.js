async a=>{
 const fail=(r,d={})=>{throw Error(r+':'+JSON.stringify(d))};
 const union=rs=>{rs=rs.filter(r=>r&&r.w>0&&r.h>0);if(!rs.length)return null;const x=Math.min(...rs.map(r=>r.x)),y=Math.min(...rs.map(r=>r.y));return{x,y,w:Math.max(...rs.map(r=>r.x+r.w))-x,h:Math.max(...rs.map(r=>r.y+r.h))-y}};
 const rect=b=>({x:b.x,y:b.y,w:b.width,h:b.height});
 if(a.action==='init'){
  document.body.style.cssText='margin:0;padding:0;overflow:hidden;background:white';
  const doc=mxUtils.parseXml(a.xml),models=doc.getElementsByTagName('mxGraphModel');if(models.length!==1)fail('editing_requires_one_native_model');const model=models[0];
  for(const declaration of(model.getAttribute('extFonts')||'').split('|')){if(!declaration)continue;const i=declaration.indexOf('^'),family=declaration.slice(0,i),uri=declaration.slice(i+1);if(i<1||!uri.startsWith('data:'))fail('editing_font_not_closed');const font=new FontFace(family,'url('+JSON.stringify(uri)+')');document.fonts.add(await font.load());}
  const box=document.createElement('div');box.style.cssText='position:absolute;left:0;top:0;overflow:hidden;width:'+a.width+'px;height:'+a.height+'px;background:white';document.body.append(box);
  const g=new Graph(box);g.setEnabled(true);g.setPanning(false);new mxCodec(doc).decode(model,g.model);g.view.scaleAndTranslate(1,0,0);
  const encode=()=>mxUtils.getXml(new mxCodec().encode(g.model));
  const allStates=()=>Object.fromEntries(Object.values(g.model.cells).map(c=>{const s=g.view.getState(c);return[c.id,s?{x:s.x,y:s.y,w:s.width,h:s.height,absolutePoints:s.absolutePoints?.map(p=>p?[p.x,p.y]:null)||null}:null]}));
  const paint=()=>JSON.stringify(Object.values(g.model.cells).filter(c=>c.vertex).map(c=>{const s=g.view.getState(c);return[c.id,s?.shape?.node?.outerHTML,s?.text?.node?.outerHTML]}));
  const images=new Map();
  const tick=async()=>{g.refresh();g.view.validate();for(const n of g.container.querySelectorAll('img,image')){const u=n.currentSrc||(typeof n.src==='string'?n.src:null)||n.getAttribute('href')||n.getAttributeNS('http://www.w3.org/1999/xlink','href');if(!u)continue;if(!u.startsWith('data:'))fail('editing_image_not_closed');if(!images.has(u)){const im=new Image();im.src=u;images.set(u,im.decode())}}await Promise.all(images.values());await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))};
  const visible=n=>{for(let e=n.parentElement;e&&e!==box;e=e.parentElement){const c=getComputedStyle(e);if(c.display==='none'||c.visibility!=='visible'||+c.opacity===0)return false;}return true};
  const clip=(r,n)=>{for(let e=n.parentElement;e&&e!==box;e=e.parentElement){const c=getComputedStyle(e),b=e.getBoundingClientRect();if(['hidden','clip','scroll','auto'].includes(c.overflowX)){const x=Math.max(r.x,b.x),right=Math.min(r.x+r.w,b.right);r={...r,x,w:right-x}}if(['hidden','clip','scroll','auto'].includes(c.overflowY)){const y=Math.max(r.y,b.y),bottom=Math.min(r.y+r.h,b.bottom);r={...r,y,h:bottom-y}}if(r.w<=0||r.h<=0)return null;}return r};
  const support=id=>{
   const c=g.model.getCell(id),desc=g.model.getDescendants(c).filter(x=>x.vertex),rs=[];let glyphRects=0,textNodes=0;
   for(const owner of desc){const s=g.view.getState(owner);if(!s)continue;rs.push({x:s.x,y:s.y,w:s.width,h:s.height});const roots=[...new Set([s.shape?.node,s.text?.node].filter(Boolean))];
    for(const root of roots){for(const n of root.querySelectorAll('path,rect,circle,ellipse,polygon,polyline,line,image,img')){const b=n.getBoundingClientRect(),css=getComputedStyle(n);if(!(b.width>0&&b.height>0)||css.visibility!=='visible'||css.display==='none'||+css.opacity===0)continue;const image=['image','img'].includes(n.tagName.toLowerCase()),fill=css.fill!=='none'&&css.fill!=='transparent'&&+css.fillOpacity!==0,stroke=css.stroke!=='none'&&css.stroke!=='transparent'&&+css.strokeOpacity!==0&&parseFloat(css.strokeWidth)>0;if(!image&&!fill&&!stroke)continue;let pad=2;if(n instanceof SVGElement&&stroke){const m=n.getScreenCTM?.(),scale=m?Math.sqrt(m.a*m.a+m.b*m.b+m.c*m.c+m.d*m.d):1;pad+=parseFloat(css.strokeWidth||0)*scale*Math.max(1,parseFloat(css.strokeMiterlimit||1))/2;}rs.push({x:b.x-pad,y:b.y-pad,w:b.width+2*pad,h:b.height+2*pad});}
     const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim()||!visible(n))continue;textNodes++;const range=document.createRange();range.selectNodeContents(n);const css=getComputedStyle(n.parentElement),pad=Math.max(2,parseFloat(css.fontSize)||0);for(const b of range.getClientRects()){if(!(b.width>0&&b.height>0))continue;const r=clip({x:b.x-pad,y:b.y-pad,w:b.width+2*pad,h:b.height+2*pad},n);if(r){rs.push(r);glyphRects++;}}}
    }
   }
   const b=union(rs);return{cell:id,bbox:b,actual_live_glyph_line_rectangles:glyphRects,actual_nonempty_visible_Text_nodes:textNodes,native_descendants_included:desc.map(x=>x.id)};
  };
  const mutate=value=>{const box=document.createElement('div');box.innerHTML=String(value);const walker=document.createTreeWalker(box,NodeFilter.SHOW_TEXT),nodes=[];let n;while(n=walker.nextNode())if(n.textContent.trim())nodes.push(n);if(!nodes.length)fail('paragraph_edit_no_original_nonempty_Text_nodes');for(const n of nodes){n.textContent='QACONTROL '+n.textContent;const p=n.parentElement;p.style.setProperty('color','#ef003a','important');p.style.setProperty('-webkit-text-fill-color','#ef003a','important');}return{value:box.innerHTML,original_nonempty_Text_nodes:nodes.length,all_nonempty_original_Text_nodes_edited:true};};
  await tick();const objects=Object.values(g.model.cells).filter(c=>c.vertex).map(c=>{if(!c.geometry||c.geometry.relative||!g.isCellMovable(c)||!g.isCellEditable(c))fail('native_owner_not_individually_movable_editable_absolute_vertex',{cell:c.id});const ancestors=[];for(let p=c.parent;p;p=p.parent)ancestors.push(p.id);return{cell:c.id,paragraph:c.id.startsWith('source_paragraph_owner_'),ancestor_ids:ancestors};});
  const p={g,encode,allStates,paint,tick,support,mutate,objects,saved:{},before:encode(),beforeStates:JSON.stringify(allStates()),beforePaint:paint(),size:{w:a.width,h:a.height}};window.__htmlFlexEditV3=p;
  const rows=objects.map(o=>({...o,support:support(o.cell)}));return{objects:rows,size:[a.width,a.height],actual_native_image_resources_decoded:images.size,fonts_ready:document.fonts.status==='loaded',baseline_model_sha_basis:p.before};
 }
 const p=window.__htmlFlexEditV3;if(!p)fail('native_editing_runtime_not_initialized');const g=p.g;
 const restored=()=>{const model=p.encode()===p.before,states=JSON.stringify(p.allStates())===p.beforeStates,paint=p.paint()===p.beforePaint;if(!model||!states||!paint)fail('complete_native_model_states_or_DOM_not_restored',{model,states,paint});return{whole_model_restored:model,all_native_states_restored:states,whole_actual_paint_DOM_restored:paint}};
 if(a.action==='plan_text'){
  const rows=[];
  for(const obj of p.objects.filter(o=>o.paragraph)){const c=g.model.getCell(obj.cell),old=c.value,before=p.support(c.id),changed=p.mutate(old);g.model.setValue(c,changed.value);g.view.validate();const after=p.support(c.id);g.model.setValue(c,old);g.view.validate();if(p.encode()!==p.before)fail('text_support_planning_changed_model');rows.push({...obj,before,after,original_nonempty_Text_nodes:changed.original_nonempty_Text_nodes,all_nonempty_original_Text_nodes_edited:true});}
  await p.tick();restored();return rows;
 }
 if(a.action==='apply'){
  if(Object.keys(p.saved).length)fail('editing_batch_started_before_restore');const result=[];
  g.model.beginUpdate();try{for(const id of a.ids){const c=g.model.getCell(id),s=g.view.getState(c);p.saved[id]={geometry:c.geometry,value:c.value,state:{x:s.x,y:s.y},paint:s.shape?.node?.outerHTML,text:s.text?.node?.outerHTML};
    if(a.kind==='move'){const geo=c.geometry.clone();geo.x+=17;geo.y+=11;g.model.setGeometry(c,geo);result.push({cell:id});}
    else{const changed=p.mutate(c.value);g.model.setValue(c,changed.value);result.push({cell:id,original_nonempty_Text_nodes:changed.original_nonempty_Text_nodes,all_nonempty_original_Text_nodes_edited:true,value_changed:c.value!==p.saved[id].value});}
  }}finally{g.model.endUpdate()}await p.tick();
  return result.map(r=>{const c=g.model.getCell(r.cell),s=g.view.getState(c),saved=p.saved[r.cell];if(a.kind==='move'){const delta=[s.x-saved.state.x,s.y-saved.state.y];if(delta[0]!==17||delta[1]!==11)fail('native_actual_state_move_not_exact_17_11',{cell:r.cell,delta});r.actual_state_delta=delta;r.actual_paint_DOM_changed=s.shape?.node?.outerHTML!==saved.paint||s.text?.node?.outerHTML!==saved.text;if(!r.actual_paint_DOM_changed)fail('native_owner_move_no_actual_DOM_change',{cell:r.cell});}else{const text=(s.text?.node?.textContent||'')+(s.shape?.node?.textContent||'');r.actual_live_text_changed=text.includes('QACONTROL');if(!r.value_changed||!r.actual_live_text_changed)fail('paragraph_model_or_actual_Text_edit_missing',{cell:r.cell});}return{...r,after_support:p.support(r.cell)}});
 }
 if(a.action==='restore'){
  const ids=Object.keys(p.saved);g.model.beginUpdate();try{for(const id of ids){const c=g.model.getCell(id),saved=p.saved[id];if(a.kind==='move')g.model.setGeometry(c,saved.geometry);else g.model.setValue(c,saved.value);}}finally{g.model.endUpdate()}await p.tick();const proof=restored();const rows=ids.map(id=>({cell:id,...proof,geometry_restored:g.model.getCell(id).geometry===p.saved[id].geometry}));p.saved={};return rows;
 }
 if(a.action==='snapshot')return{model:p.encode(),states:p.allStates(),paint:p.paint(),whole_model_restored:p.encode()===p.before,whole_actual_paint_DOM_restored:p.paint()===p.beforePaint};
 if(a.action==='dispose'){restored();g.destroy();delete window.__htmlFlexEditV3;return{ok:true};}
 fail('unknown_native_edit_action');
}
