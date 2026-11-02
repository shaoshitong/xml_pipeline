from pathlib import Path
D=Path(__file__).parent
if not(D/'compiler_svg_scene_frontend_v12.py').exists():D=D.parent/'conversion/scripts'

def write(name,s):
 p=D/name
 if p.exists():assert p.read_text()==s,name
 else:p.write_text(s)
# Preserve proven source group identity while preventing duplicate DOM IDs from
# invalidating Chromium's original <use> UA shadows during source observation.
for old,new in [('svg_dom_v9.js','svg_dom_v10.js'),('svg_dom_source_scene_v4.js','svg_dom_source_scene_v5.js')]:
 s=(D/old).read_text();oldline='g.appendChild(src.cloneNode(true));root.appendChild(g);';newLine="const clone=src.cloneNode(true);clone.removeAttribute('id');if(clone.querySelector('[id]'))throw Error('source_group_descendant_ids_require_reference_remapping');g.appendChild(clone);root.appendChild(g);"
 assert s.count(oldline)==1;s=s.replace(oldline,newLine);write(new,s)
s=(D/'svg_source_use_instance_proof_v4.py').read_text();s=s.replace('g.appendChild(src.cloneNode(true));root.appendChild(g);',"const clone=src.cloneNode(true);clone.removeAttribute('id');if(clone.querySelector('[id]'))throw Error('source_group_descendant_ids_require_reference_remapping');g.appendChild(clone);root.appendChild(g);")
s=s.replace(".map(e=>{if(!allowed.has(e.localName))", ".map((e,i)=>{if(!allowed.has(e.localName))")
s=s.replace("attributes:[...e.attributes].map(a=>[a.name,a.value])", "attributes:[...e.attributes].filter(a=>i!==0||a.name!=='id').map(a=>[a.name,a.value])")
s=s.replace('actual_UA_use_shadow_and_exact_clone_layout_quads_vector_paint_v3','actual_UA_use_shadow_and_exact_clone_layout_quads_vector_paint_v4')
write('svg_source_use_instance_proof_v5.py',s)
s=(D/'svg_source_endpoint_bridge_v3.py').read_text().replace('svg_dom_v9.js','svg_dom_v10.js').replace('svg_dom_source_scene_v4.js','svg_dom_source_scene_v5.js');write('svg_source_endpoint_bridge_v4.py',s)
s=(D/'svg_source_edge_layers_v1.py').read_text().replace('def repair(dom,xml,size):\n from compiler_svg_scene_backend_v10 import derive','def repair(dom,xml,size,*,semantic,binding):').replace(" semantic,binding=derive(dom,size);objects={o['id']:o for o in semantic['objects']};source_objects=",' source_objects=')
write('svg_source_edge_layers_v2.py',s)
s=(D/'compiler_svg_scene_backend_v10.py').read_text().replace('svg_source_use_instance_proof_v3','svg_source_use_instance_proof_v5').replace("POLICY='generic_source_svg_analytic_endpoint_native_curve_nested_groups_proved_use_v8'","POLICY='generic_source_svg_source_group_owned_edge_layers_duplicate_ID_safe_use_v11'")
s=s.replace(' return xml,stats\n',' from svg_source_edge_layers_v2 import repair\n xml,layers=repair(dom,xml,size,semantic=semantic,binding=proof);stats[\'source_edge_layers\']=layers\n return xml,stats\n');write('compiler_svg_scene_backend_v11.py',s)
s=(D/'compiler_svg_explicit_coordinates_v5.py').read_text().replace('compiler_svg_scene_backend_v10','compiler_svg_scene_backend_v11').replace('proved_use_coverage_v3','source_group_owned_edge_layers_coverage_v6')
s=s.replace("style=_style(edge);geo=edge.find('mxGeometry');require(geo is not None,'missing_edge_geometry');ends=[]", "style=_style(edge);geo=edge.find('mxGeometry');require(geo is not None,'missing_edge_geometry');parent=cells.get(edge.get('parent'));origin=_world_box(parent,cells)[:2]if parent is not None and parent.get('vertex')=='1'else(0,0);ends=[]")
s=s.replace("point=tuple(float(matches[0].get(k,'nan')) for k in ('x','y'))", "point=tuple(float(matches[0].get(k,'nan'))+origin[i]for i,k in enumerate(('x','y')))")
s=s.replace("bends=[tuple(float(p.get(k,'nan')) for k in ('x','y')) for p", "bends=[tuple(float(p.get(k,'nan'))+origin[i]for i,k in enumerate(('x','y'))) for p")
write('compiler_svg_explicit_coordinates_v6.py',s);write('compiler_svg_explicit_coordinates_v6.js',(D/'compiler_svg_explicit_coordinates_v5.js').read_text())
s=(D/'compiler_svg_scene_frontend_v13.py').read_text();mapping={'compiler_svg_scene_frontend_v13':'compiler_svg_scene_frontend_v14','native_symbol_viewport_v13':'source_owned_edge_layers_duplicate_ID_safe_use_v14','svg_source_use_instance_proof_v4':'svg_source_use_instance_proof_v5','svg_source_endpoint_bridge_v3':'svg_source_endpoint_bridge_v4','svg_dom_v9.js':'svg_dom_v10.js','svg_dom_source_scene_v4.js':'svg_dom_source_scene_v5.js','compiler_svg_scene_backend_v10':'compiler_svg_scene_backend_v11','compiler_svg_explicit_coordinates_v5':'compiler_svg_explicit_coordinates_v6'}
for a,b in mapping.items():s=s.replace(a,b)
s=s.replace("DEPENDENCIES=(VERSION+'.py',", "DEPENDENCIES=(VERSION+'.py','svg_source_edge_layers_v2.py',")
write('compiler_svg_scene_frontend_v14.py',s)
s=(D/'compiler_svg_general_guard_v9.py').read_text().replace('compiler_svg_scene_frontend_v13','compiler_svg_scene_frontend_v14').replace('compiler_svg_scene_backend_v10','compiler_svg_scene_backend_v11').replace('general_svg_v13_native_symbol_viewport_source_compositing_order_guard_v9','general_svg_v14_source_owned_edge_layers_duplicate_ID_safe_use_guard_v10');write('compiler_svg_general_guard_v10.py',s)
s=(D/'compiler_svg_general_quality_adapter_v11.py').read_text().replace('compiler_svg_general_guard_v9','compiler_svg_general_guard_v10').replace('QA_single_fill_leaf_opacity_v11','QA_source_edge_layers_safe_use_leaf_opacity_v12').replace("'svg_source_use_instance_proof_v3.py'","'svg_source_use_instance_proof_v5.py'");write('compiler_svg_general_quality_adapter_v12.py',s)
s=(D/'compiler_svg_scene_quality_ro_v15.py').read_text().replace('compiler_svg_general_guard_v9','compiler_svg_general_guard_v10').replace('compiler_svg_general_quality_adapter_v11','compiler_svg_general_quality_adapter_v12').replace('native_symbol_viewport_single_fill_leaf_alpha_v15','source_owned_edge_layers_duplicate_ID_safe_use_leaf_alpha_v16');write('compiler_svg_scene_quality_ro_v16.py',s)
s=(D/'svg_native_symbol_viewport_normal_dev_v1.py').read_text().replace('compiler_svg_general_guard_v9','compiler_svg_general_guard_v10').replace('compiler_svg_scene_quality_ro_v14','compiler_svg_scene_quality_ro_v16').replace('SVG_native_symbol_viewport_v13_','SVG_source_owned_edge_layers_v14_');write('svg_source_owned_edge_layers_normal_dev_v1.py',s)
print('created immutable edge-layer and duplicate-ID-safe successors')
