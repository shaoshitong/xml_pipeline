({mode,dom})=>{
 const req=(ok,reason)=>{if(!ok)throw Error(reason)},segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
 const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height});
 if(mode==='begin'){
  const items=[];
  if(dom){const nodes=window.__img2codeAlignTextNodes;for(let i=0;i<nodes.length;i++)items.push({node:nodes[i],cells:dom.objects.filter(o=>o.type==='text'&&o.actualSourceTextNode===i).map(o=>String(o.id+1))});}
  else{const g=window.evalViewer.graph;for(const c of Object.values(g.model.cells)){const state=g.view.getState(c);if(!state?.text?.node)continue;const w=document.createTreeWalker(state.text.node,NodeFilter.SHOW_TEXT);while(w.nextNode())if(w.currentNode.textContent.length)items.push({node:w.currentNode,cells:[c.id]});}}
  const snapshot=item=>{const n=item.node,cs=getComputedStyle(n.parentElement),chars=[];for(const {segment,index}of segmenter.segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);chars.push({text:segment,start:index,...rect(r.getBoundingClientRect())});}const svg=n.parentElement.closest('foreignObject'),m=svg?.getScreenCTM();return {text:n.textContent,chars,font:cs.font,fontFamily:cs.fontFamily,fontSize:cs.fontSize,fontWeight:cs.fontWeight,fontStyle:cs.fontStyle,lineHeight:cs.lineHeight,verticalAlign:cs.verticalAlign,display:cs.display,transform:cs.transform,textRendering:cs.textRendering,fontKerning:cs.fontKerning,foreignObjectCTM:m?[m.a,m.b,m.c,m.d,m.e,m.f]:null};};
  const before=items.map(snapshot);for(let i=0;i<items.length;i++)items[i].measurable=dom?Boolean(dom._baseline_probe_cells?.some(k=>items[i].cells.includes(k))):(!before[i].text.includes('\n')&&new Set(before[i].chars.filter(x=>x.width>0&&x.height>0).map(x=>x.y)).size===1);window.__cssBaselineProbeV1={items,snapshot,before,markers:[]};return {nodes:items.length,phase:'before',rows:items.map((x,i)=>({cells:x.cells,...window.__cssBaselineProbeV1.before[i]}))};
 }
 const p=window.__cssBaselineProbeV1;req(p,'baseline_probe_not_started');
 if(mode==='insert'){
  for(const item of p.items){if(!item.measurable){p.markers.push(null);continue;}const marker=document.createElement('img2code-baseline-probe');marker.style.cssText='all:initial!important;display:inline-block!important;vertical-align:baseline!important;position:static!important;width:0!important;height:0!important;line-height:0!important;font-size:0!important;margin:0!important;padding:0!important;border:0!important;opacity:0!important;overflow:hidden!important;';item.node.parentNode.insertBefore(marker,item.node.nextSibling);p.markers.push(marker);}
  return {phase:'inserted',rows:p.items.map((x,i)=>({cells:x.cells,baseline:p.markers[i]?rect(p.markers[i].getBoundingClientRect()):null,measurable:x.measurable,markerStyle:p.markers[i]?{display:getComputedStyle(p.markers[i]).display,verticalAlign:getComputedStyle(p.markers[i]).verticalAlign,lineHeight:getComputedStyle(p.markers[i]).lineHeight,fontSize:getComputedStyle(p.markers[i]).fontSize}:null,before:p.before[i],after:p.snapshot(x)}))};
 }
 if(mode==='restore'){
  for(const m of p.markers)if(m)m.remove();const after=p.items.map(p.snapshot),same=JSON.stringify(p.before)===JSON.stringify(after);delete window.__cssBaselineProbeV1;return {phase:'restored',all_original_text_font_and_grapheme_ranges_exact:same};
 }
 throw Error('unknown_baseline_probe_phase');
}
