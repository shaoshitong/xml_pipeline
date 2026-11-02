async p=>{
 const fail=(r,d={})=>{throw Error(r+':'+JSON.stringify(d))},s=window.__sourceImageProbe,g=s?.g;if(!g)fail('gradient_real_graph_not_initialized');
 const tick=async()=>{g.refresh();g.view.validate();await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))};
 const color=v=>{const c=document.createElement('canvas').getContext('2d');c.fillStyle=v;return c.fillStyle.toLowerCase()};
 const unit=v=>String(v).endsWith('%')?parseFloat(v)/100:parseFloat(v);
 const expectedCoordinates={east:[0,0,1,0],west:[1,0,0,0],south:[0,0,0,1],north:[0,1,0,0]};
 const inspect=e=>{
  const cell=g.model.getCell(e.native_cell_id),state=g.view.getState(cell);if(!cell?.vertex||!state?.shape?.node||!g.isCellMovable(cell))fail('gradient_not_real_individually_editable_vertex',{id:e.native_cell_id});
  const node=state.shape.node,paints=[node,...node.querySelectorAll('*')].filter(n=>!n.closest('defs')&&String(getComputedStyle(n).fill).includes('url('));if(!paints.length)fail('gradient_no_actual_native_gradient_painter',{id:e.native_cell_id});
  const observations=[];
  for(const paint of paints){const fill=getComputedStyle(paint).fill,id=fill.match(/#([^"')]+)["']?\)/)?.[1],grad=document.getElementById(id);if(!grad||grad.localName!=='linearGradient')fail('gradient_actual_paint_not_local_linearGradient',{fill});
   if(grad.getAttribute('gradientUnits')&&grad.getAttribute('gradientUnits')!=='objectBoundingBox'||grad.hasAttribute('gradientTransform')||grad.hasAttribute('href')||grad.hasAttributeNS('http://www.w3.org/1999/xlink','href'))fail('gradient_actual_coordinate_system_changed');
   const coordinates=['x1','y1','x2','y2'].map(k=>unit(grad.getAttribute(k)||'0%')),want=expectedCoordinates[e.direction];if(coordinates.some((v,i)=>Math.abs(v-want[i])>1e-8))fail('gradient_actual_full_axis_direction_changed',{coordinates,want});
   const stops=[...grad.querySelectorAll('stop')].map(x=>({offset:unit(x.getAttribute('offset')),color:color(getComputedStyle(x).stopColor),opacity:+getComputedStyle(x).stopOpacity}));
   if(stops.length!==2||stops.some((v,i)=>v.offset!==i||v.color!==e.colors[i]||Math.abs(v.opacity-e.stop_opacities[i])>1e-8))fail('gradient_actual_original_stops_changed',{stops,wanted:e});
   const b=paint.getBoundingClientRect();observations.push({gradient_id:id,coordinates,stops,actual_fill:fill,paint_bbox:{x:b.x,y:b.y,w:b.width,h:b.height}});
  }
  return {native_cell_id:e.native_cell_id,movable:g.isCellMovable(cell),actual_native_gradient_painters:observations};
 };
 const inspectStroke=e=>{
  const cell=g.model.getCell(e.native_cell_id),state=g.view.getState(cell),roots=[...new Set([state?.text?.node,state?.shape?.node].filter(Boolean))];
  // shape=text paints through state.shape; other label owners use state.text.
  // Original model markup is independently exact-checked. Sanitized DOM need
  // not retain private data attributes: require the real source-text painter.
  const spans=[...new Set(roots.flatMap(n=>[...(n.matches?.('span')?[n]:[]),...n.querySelectorAll('span')]))].filter(n=>n.textContent===e.original_text&&parseFloat(getComputedStyle(n).webkitTextStrokeWidth)>0);
  if(!cell?.vertex||!spans.length)fail('source_text_stroke_has_no_actual_native_HTML_painter',{id:e.native_cell_id,shapeKind:state?.shape?.constructor?.name,rootCount:roots.length});const span=spans[0],css=getComputedStyle(span),width=parseFloat(css.webkitTextStrokeWidth),stroke=color(css.webkitTextStrokeColor);
  if(Math.abs(width-e.source_screen_stroke_width)>1e-8||stroke!==e.source_stroke_color||css.paintOrder!==e.source_paint_order)fail('actual_native_original_text_stroke_changed',{id:e.native_cell_id,width,stroke,paintOrder:css.paintOrder,wanted:e});
  return {native_cell_id:e.native_cell_id,actual_screen_stroke_width:width,actual_source_stroke_color:stroke,actual_paint_order:css.paintOrder,actual_text:span.textContent};
 };
 const inspectAlpha=e=>{
  const cell=g.model.getCell(e.native_cell_id),state=g.view.getState(cell);if(!cell?.vertex||!state?.shape?.node)fail('single_alpha_missing_actual_stencil_painter');
  const paints=[state.shape.node,...state.shape.node.querySelectorAll('*')].filter(n=>['path','rect','circle','ellipse','polygon','polyline'].includes(n.localName)&&!n.closest('defs')&&getComputedStyle(n)[e.mode]!=='none');if(!paints.length)fail('single_alpha_no_actual_paint');
  const actual=paints.map(n=>{const css=getComputedStyle(n);let alpha=+css[e.mode+'Opacity'];for(let p=n;p&&p!==g.container;p=p.parentElement)alpha*=+getComputedStyle(p).opacity;const c=color(css[e.mode]);if(c!==e.color||Math.abs(alpha-e.effective_alpha)>1e-8)fail('single_original_paint_actual_alpha_or_color_changed',{actual:alpha,color:c,wanted:e});return {effective_alpha:alpha,color:c}});return {native_cell_id:e.native_cell_id,actual_paints:actual};
 };
 if(p.action==='inspect'){
  await Promise.all([...g.container.querySelectorAll('image')].map(async n=>{const uri=n.getAttribute('href')||n.getAttributeNS('http://www.w3.org/1999/xlink','href');if(!uri?.startsWith('data:image/'))fail('gradient_probe_source_image_not_closed');const im=new Image();im.src=uri;await im.decode()}));await tick();window.__sourceGradientProbe={rows:p.expected,strokes:p.expected_strokes||[],alpha:p.expected_alpha||[],baselineModel:s.encode(),baselineStates:JSON.stringify(s.allStates()),saved:{},savedText:{},savedAlpha:{}};return {gradients:p.expected.map(inspect),source_text_strokes:(p.expected_strokes||[]).map(inspectStroke),single_paint_alpha:(p.expected_alpha||[]).map(inspectAlpha)};
 }
 const probe=window.__sourceGradientProbe;if(!probe)fail('gradient_probe_not_initialized');
 if(p.action==='edit_alpha'||p.action==='restore_alpha'){
  const e=probe.alpha.find(r=>r.native_cell_id===p.id),cell=g.model.getCell(p.id);if(!e||!cell)fail('single_alpha_owner_missing');
  if(p.action==='edit_alpha'){if(probe.savedAlpha[p.id]!==undefined)fail('single_alpha_duplicate_edit');probe.savedAlpha[p.id]=cell.style;g.setCellStyles('opacity','100',[cell]);await tick();return {id:p.id,actual_mutation:'set_single_paint_opacity_to_100',original_source_opacity:e.source_element_opacity};}
  const style=probe.savedAlpha[p.id];if(style===undefined)fail('single_alpha_restore_without_original');g.model.setStyle(cell,style);delete probe.savedAlpha[p.id];await tick();if(s.encode()!==probe.baselineModel||JSON.stringify(s.allStates())!==probe.baselineStates)fail('single_alpha_model_or_states_not_restored');return {id:p.id,original_single_painter:inspectAlpha(e),model_exactly_restored:true,all_states_exactly_restored:true};
 }
 if(p.action==='edit_stroke'||p.action==='restore_stroke'){
  const e=probe.strokes.find(r=>r.native_cell_id===p.id),cell=g.model.getCell(p.id);if(!e||!cell)fail('source_text_stroke_probe_owner_missing');
  if(p.action==='edit_stroke'){
   if(probe.savedText[p.id]!==undefined)fail('source_text_stroke_duplicate_edit');probe.savedText[p.id]=cell.value;const box=document.createElement('div');box.innerHTML=String(cell.value);const span=box.querySelector('[data-compiler-source-text-stroke-v1="true"]');if(!span)fail('source_text_stroke_original_markup_missing');span.style.webkitTextStrokeWidth='0px';g.model.setValue(cell,box.innerHTML);await tick();return {id:p.id,original_source_stroke_width:e.source_screen_stroke_width,actual_mutation:'remove_text_stroke_only',original_Unicode_unchanged:box.textContent===e.original_text};
  }
  const value=probe.savedText[p.id];if(value===undefined)fail('source_text_stroke_restore_without_saved_value');g.model.setValue(cell,value);delete probe.savedText[p.id];await tick();const modelExact=s.encode()===probe.baselineModel,statesExact=JSON.stringify(s.allStates())===probe.baselineStates;if(!modelExact||!statesExact)fail('source_text_stroke_model_or_states_not_restored');return {id:p.id,model_exactly_restored:modelExact,all_states_exactly_restored:statesExact,original_stroke_painter:inspectStroke(e)};
 }
 const wanted=probe.rows.find(r=>r.native_cell_id===p.id),cell=g.model.getCell(p.id);if(!wanted||!cell)fail('gradient_probe_owner_missing');
 if(p.action==='edit'){
  if(probe.saved[p.id]!==undefined)fail('gradient_duplicate_mutation');probe.saved[p.id]=cell.style;const mutation=wanted.colors[1]==='#e040d0'?'#13df4a':'#e040d0';g.setCellStyles('gradientColor',mutation,[cell]);await tick();return {id:p.id,actual_style_mutation:g.getCellStyle(cell).gradientColor,original_source_gradient_color:wanted.colors[1],mutation};
 }
 if(p.action==='restore'){
  const style=probe.saved[p.id];if(style===undefined)fail('gradient_restore_without_saved_original');g.model.beginUpdate();try{g.model.setStyle(cell,style)}finally{g.model.endUpdate()}delete probe.saved[p.id];await tick();
  const modelExact=s.encode()===probe.baselineModel,statesExact=JSON.stringify(s.allStates())===probe.baselineStates;if(!modelExact||!statesExact)fail('gradient_model_or_states_not_exactly_restored',{modelExact,statesExact});return {id:p.id,model_exactly_restored:modelExact,all_native_states_exactly_restored:statesExact,restored_original_painter:inspect(wanted)};
 }
 fail('gradient_unknown_probe_action');
}
