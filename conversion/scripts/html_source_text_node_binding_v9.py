"""Caller identity binding for exact live Text objects, including whitespace."""
def physical_fonts_for_object(session,text_object_id,parent_node_id,child_index,expected_text):
 from compiler_native_text_node_cdp_v2 import physical_fonts
 original=session.send('DOM.describeNode',{'objectId':text_object_id,'depth':0})['node']
 if original.get('nodeType')!=3 or original.get('nodeValue')!=expected_text:raise ValueError('paragraph_original_live_Text_object_changed')
 children=session.send('DOM.describeNode',{'nodeId':parent_node_id,'depth':1})['node'].get('children',[])
 if not isinstance(child_index,int)or not 0<=child_index<len(children)or children[child_index].get('backendNodeId')!=original.get('backendNodeId'):raise ValueError('paragraph_actual_Text_object_not_exact_original_parent_child_backend')
 fonts=physical_fonts(session,parent_node_id,child_index,expected_text)
 current=session.send('DOM.describeNode',{'objectId':text_object_id,'depth':0})['node']
 if current.get('backendNodeId')!=original.get('backendNodeId')or current.get('nodeValue')!=expected_text:raise ValueError('paragraph_original_live_Text_object_changed_after_fonts')
 return fonts,{'basis':'original_live_Text_object_exact_parent_child_backend','backendNodeId':original['backendNodeId'],'original_child_index':child_index,'pure_whitespace':expected_text.isspace()}
