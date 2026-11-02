/* Source original text-node templates -> actual native DOM, no source mutation.
 * Uses the runtime's own label/placeholder APIs, not a guessed variable list.
 * Empty expansions remain raw in the source; markup-producing expansions are
 * typed pending. Non-null environment/global lookups are never frozen as text.
 */
window.nativeSourceLabelTemplateBindingV1 = function(graph, cell, liveTexts) {
  const fail = reason => { throw Error(reason); };
  const value = graph.model.getValue(cell), object = value && typeof value === 'object';
  const enabled = !!graph.isReplacePlaceholders(cell);
  if (object && enabled && value.getAttribute('placeholder') != null) {
    return {rich_rewrite_allowed:false,indirect_scalar_property:true,
      source_property_key:value.getAttribute('placeholder'),
      original_object_properties_must_remain_unchanged:true};
  }
  let attribute='value', raw;
  if (object) {
    attribute=Graph.translateDiagram && Graph.diagramLanguage &&
      value.hasAttribute('label_'+Graph.diagramLanguage) ? 'label_'+Graph.diagramLanguage : 'label';
    raw=value.getAttribute(attribute)||'';
  } else raw=value==null?'':String(value);
  const fragment = html => {const d=document.createElement('div');d.innerHTML=Graph.sanitizeHtml(html);return d;};
  const texts = root => {const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode())if(w.currentNode.textContent.length)out.push(w.currentNode);return out;};
  const originalGlobal=graph.getGlobalVariable, lookups=[];
  graph.getGlobalVariable=function(name){const result=originalGlobal.apply(this,arguments);lookups.push({name,is_null:result==null});return result;};
  let expected,actual,marked,rawFragment,rawNodes;
  try {
    expected=enabled?graph.replacePlaceholders(cell,raw):raw;
    actual=graph.getLabel(cell);
    if(expected!==actual)fail('typed_original_source_label_carrier_not_the_actual_native_label');
    rawFragment=fragment(raw);rawNodes=texts(rawFragment);
    if(rawFragment.querySelector('[data-native-source-template-probe-v1]'))fail('typed_source_template_probe_attribute_conflict');
    rawNodes.forEach((node,index)=>{const span=document.createElement('span');span.setAttribute('data-native-source-template-probe-v1',String(index));node.replaceWith(span);span.append(node);});
    marked=fragment(enabled?graph.replacePlaceholders(cell,rawFragment.innerHTML):rawFragment.innerHTML);
  } finally {graph.getGlobalVariable=originalGlobal;}
  if(lookups.some(row=>!row.is_null))fail('typed_source_environment_label_variable_requires_explicit_source_provenance');
  const expectedFragment=fragment(expected), inverse=marked.cloneNode(true);
  for(const span of inverse.querySelectorAll('[data-native-source-template-probe-v1]'))span.replaceWith(...span.childNodes);
  if(!inverse.isEqualNode(expectedFragment))fail('typed_source_template_probe_changed_native_placeholder_expansion');
  const wanted=texts(expectedFragment).map(n=>n.textContent);
  if(JSON.stringify(wanted)!==JSON.stringify(liveTexts))fail('typed_source_template_native_DOM_text_node_binding_mismatch');
  const nodes=[];let actualIndex=0;
  rawNodes.forEach((node,index)=>{
    const matches=marked.querySelectorAll('[data-native-source-template-probe-v1="'+index+'"]');
    if(matches.length!==1)fail('typed_source_template_probe_node_not_unique');
    const span=matches[0];
    if(Array.from(span.childNodes).some(n=>n.nodeType!==Node.TEXT_NODE))fail('typed_source_placeholder_expands_to_markup_pending');
    const resolved=span.textContent;
    if(resolved===''){nodes.push({source_index:index,raw_text:node.textContent,resolved_text:'',actual_run_index:null,preserve_empty_expansion:true});return;}
    if(liveTexts[actualIndex]!==resolved)fail('typed_source_template_one_to_one_text_node_binding_pending');
    nodes.push({source_index:index,raw_text:node.textContent,resolved_text:resolved,actual_run_index:actualIndex++,preserve_empty_expansion:false});
  });
  if(actualIndex!==liveTexts.length)fail('typed_source_template_native_text_coverage_incomplete');
  return {rich_rewrite_allowed:true,indirect_scalar_property:false,raw_label:raw,
    raw_label_attribute:attribute,source_storage:object?'XML_object_attribute':'mxCell_value',
    native_replace_placeholders_enabled:enabled,native_placeholder_pattern:{source:graph.placeholderPattern.source,flags:graph.placeholderPattern.flags},
    nodes,source_probe_inverse_exact:true,whole_native_label_exact:true,
    original_raw_template_and_all_object_properties_retained:true,
    non_source_global_lookup_dependencies:lookups};
};
