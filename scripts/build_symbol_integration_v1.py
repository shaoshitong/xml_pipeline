from pathlib import Path
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'

def write(name,text):
 p=D/name
 if p.exists():assert p.read_text()==text,name
 else:p.write_text(text)

setup='''
 const symbolBuilder=(__SOURCE_SYMBOL_VIEWPORT_BUILDER_V1__),symbolFacts=new WeakMap();
 const symbolHosts=[...document.querySelectorAll('svg use')].filter(e=>!e.closest('defs,symbol,marker,clipPath,mask'));
 for(const f of endpointInput.symbols||[]){if(!f.proof?.ok)continue;const e=symbolHosts[f.index];if(!e)throw Error('symbol_host_missing');const m=e.getScreenCTM(),b=e.getBoundingClientRect(),descriptor={attributes:[...e.attributes].map(a=>[a.name,a.value]),matrix:[m.a,m.b,m.c,m.d,m.e,m.f],bbox:{x:b.x,y:b.y,w:b.width,h:b.height}};if(JSON.stringify(descriptor)!==JSON.stringify(f.descriptor))throw Error('symbol_actual_host_changed');symbolFacts.set(e,f);}
'''
for old,new in [('svg_dom_v8.js','svg_dom_v9.js'),('svg_dom_source_scene_v3.js','svg_dom_source_scene_v4.js')]:
 s=(D/old).read_text().replace(' const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];',' const mat=m=>[m.a,m.b,m.c,m.d,m.e,m.f];'+setup)
 start=s.index("if(src.localName==='symbol'){const v=src.viewBox.baseVal")
 end=s.index('context=\'u\'',start) if 'source_scene' in old else s.index('useDepth++;for(const c of g.children)walk(c)',start)
 if 'source_scene' not in old:
  s=s[:start]+"const symbolFact=src.localName==='symbol'?symbolFacts.get(el):null;if(src.localName==='symbol'){if(!symbolFact)throw Error('source_symbol_actual_viewport_unproved');g=symbolBuilder(root,el,symbolFact.definition).g;}else{g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+mat(T).join(',')+')');for(const k of ['fill','stroke','strokeWidth','color','fontFamily','fontSize'])g.style[k]=cs[k];g.appendChild(src.cloneNode(true));root.appendChild(g);}"+s[end:]
 else:
  s=s[:start]+"const symbolFact=src.localName==='symbol'?symbolFacts.get(el):null;if(src.localName==='symbol'&&!symbolFact)throw Error('source_symbol_actual_viewport_unproved');\n    "+s[end:]
  start=s.index("    g=document.createElementNS('http://www.w3.org/2000/svg','g');",s.index("if(tag==='use')"))
  end=s.index('    call.syntheticCloneBBox=',start)
  s=s[:start]+"    let symbolViewport=null;if(symbolFact){const made=symbolBuilder(root,el,symbolFact.definition);g=made.g;symbolViewport=made.v;call.actualSymbolViewportProof=symbolFact.proof;}else{g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('transform','matrix('+mat(T).join(',')+')');for(const k of ['fill','stroke','strokeWidth','color','fontFamily','fontSize'])g.style[k]=cs[k];g.appendChild(src.cloneNode(true));root.appendChild(g);}\n"+s[end:]
  s=s.replace('call.syntheticCloneBBox=box(g.getBoundingClientRect());','call.syntheticViewportContainerBBox=box(g.getBoundingClientRect());call.syntheticCloneBBox=symbolViewport?sceneUnion([...symbolViewport.querySelectorAll(\'path,line,polyline,polygon,rect,circle,ellipse\')].map(e=>box(e.getBoundingClientRect()))):box(g.getBoundingClientRect());')
  s=s.replace('cloneChildren=[...g.children];call.selectorRisks','cloneChildren=[...(symbolViewport||g).children];call.selectorRisks')
  s=s.replace("if(src.localName==='symbol'&&call.sourceDefinitionOverflow!=='visible')","if(src.localName==='symbol'&&!symbolFact?.proof?.full_paint_contained_in_viewport&&call.sourceDefinitionOverflow!=='visible')")
 write(new,s)

s=(D/'svg_source_endpoint_bridge_v2.py').read_text()
s=s.replace('def capture(page,legacy=False):','def _capture(scratch,legacy,symbols):\n    page=scratch')
s=s.replace("'svg_dom_v8.js'if legacy else'svg_dom_source_scene_v3.js'","'svg_dom_v9.js'if legacy else'svg_dom_source_scene_v4.js'")
s=s.replace("script=script.replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)","script=script.replace('__SOURCE_ENDPOINT_DESCRIPTORS_V1__',describe)\n    script=script.replace('__SOURCE_SYMBOL_VIEWPORT_BUILDER_V1__',(D/'svg_source_symbol_viewport_v1.js').read_text())")
s=s.replace('dict(owners=facts,instances=list(instances.values()))','dict(owners=facts,instances=list(instances.values()),symbols=symbols)')
s+='''

def capture(page,legacy=False):
    from svg_source_symbol_viewport_v1 import collect
    # Cache fresh facts only on this immutable original observer page.
    if not hasattr(page,'_source_symbol_facts_v1'):
        page._source_symbol_facts_v1=collect(page)
    scratch=page.context.new_page()
    try:
        scratch.set_viewport_size(page.viewport_size)
        scratch.set_content(page.content())
        scratch.evaluate('()=>document.fonts.ready')
        result=_capture(scratch,legacy,page._source_symbol_facts_v1)
        result['sourceSymbolViewportFacts']=page._source_symbol_facts_v1
        return result
    finally:scratch.close()
'''
write('svg_source_endpoint_bridge_v3.py',s)
# Group ownership observer runs in an isolated page. Symbols remain unproved for
# marker ownership (old backend contract); this does not waive any marker gate.
s=(D/'svg_source_use_instance_proof_v3.py').read_text().replace('def audit(page,dom):','def _audit(page,dom):')
s+='''

def audit(page,dom):
    from copy import deepcopy
    scratch=page.context.new_page()
    try:
        scratch.set_viewport_size(page.viewport_size);scratch.set_content(page.content());scratch.evaluate('()=>document.fonts.ready')
        result=deepcopy(dom)
        contexts=result.get('sceneMetadata',{}).get('useContexts',{})
        symbols={key:value for key,value in contexts.items() if value.get('sourceDefinitionTag')=='symbol'}
        result['sceneMetadata']['useContexts']={key:value for key,value in contexts.items() if key not in symbols}
        result=_audit(scratch,result)
        result['sceneMetadata']['useContexts'].update(symbols)
        return result
    finally:scratch.close()
'''
write('svg_source_use_instance_proof_v4.py',s)
replacements={'compiler_svg_scene_frontend_v12':'compiler_svg_scene_frontend_v13','svg_source_endpoint_bridge_v2':'svg_source_endpoint_bridge_v3','svg_dom_v8.js':'svg_dom_v9.js','svg_dom_source_scene_v3.js':'svg_dom_source_scene_v4.js','svg_source_use_instance_proof_v3':'svg_source_use_instance_proof_v4','actual_shadow_layout_use_instances_v12':'native_symbol_viewport_v13'}
s=(D/'compiler_svg_scene_frontend_v12.py').read_text()
for a,b in replacements.items():s=s.replace(a,b)
s=s.replace("DEPENDENCIES=(VERSION+'.py',","DEPENDENCIES=(VERSION+'.py','svg_source_symbol_viewport_v1.py','svg_source_symbol_viewport_v1.js',")
write('compiler_svg_scene_frontend_v13.py',s)
s=(D/'compiler_svg_general_guard_v8.py').read_text().replace('compiler_svg_scene_frontend_v12','compiler_svg_scene_frontend_v13').replace('general_svg_v12_analytic_endpoint_cubic_bezier_nested_groups_actual_shadow_layout_use_instances_source_compositing_order_guard_v8','general_svg_v13_native_symbol_viewport_source_compositing_order_guard_v9')
write('compiler_svg_general_guard_v9.py',s)
s=(D/'compiler_svg_general_quality_adapter_v9.py').read_text().replace('compiler_svg_general_guard_v8','compiler_svg_general_guard_v9').replace('actual_shadow_layout_use_instances_v9','native_symbol_viewport_v10')
write('compiler_svg_general_quality_adapter_v10.py',s)
s=(D/'compiler_svg_scene_quality_ro_v13.py').read_text().replace('compiler_svg_general_guard_v8','compiler_svg_general_guard_v9').replace('compiler_svg_general_quality_adapter_v9','compiler_svg_general_quality_adapter_v10').replace('actual_shadow_layout_use_instances_v13','native_symbol_viewport_v14')
write('compiler_svg_scene_quality_ro_v14.py',s)
s=(D/'svg_actual_shadow_layout_use_instances_normal_dev_v5.py').read_text().replace('compiler_svg_general_guard_v8','compiler_svg_general_guard_v9').replace('compiler_svg_scene_quality_ro_v13','compiler_svg_scene_quality_ro_v14').replace('SVG_actual_shadow_layout_use_instances_v12_','SVG_native_symbol_viewport_v13_')
write('svg_native_symbol_viewport_normal_dev_v1.py',s)
print('created new symbol integration modules; prior production files unchanged')
