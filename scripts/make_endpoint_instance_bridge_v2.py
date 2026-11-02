"""Create immutable successor extractors; never edit an active pinned module."""
from pathlib import Path
S=Path(__file__).resolve().parent
OLD=S.parent/'xml_pipeline/conversion/scripts'
for old,new in [('svg_dom_v7.js','svg_dom_v8.js'),('svg_dom_source_scene_v2.js','svg_dom_source_scene_v3.js')]:
 code=(OLD/old).read_text()
 code=code.replace('endpointFacts => {','endpointInput => {\n const endpointFacts=endpointInput.owners,endpointRequests=[],instanceFacts=new Map(endpointInput.instances.map(f=>[JSON.stringify(f.descriptor),f]));',1)
 code=code.replace('sourceEndpointRows=(__SOURCE_ENDPOINT_DESCRIPTORS_V1__)(root)', 'describeEndpointOwners=(__SOURCE_ENDPOINT_DESCRIPTORS_V1__),sourceEndpointRows=describeEndpointOwners(root)',1)
 oldlookup="const fact=sourceEndpointMap.get(el);if(!fact)throw Error('source_analytic_endpoint_facts_missing');"
 newlookup="""let fact=sourceEndpointMap.get(el);if(!fact){const row=describeEndpointOwners(root).find(row=>row.element===el);if(!row)throw Error('source_instance_endpoint_descriptor_missing');fact=instanceFacts.get(JSON.stringify(row.descriptor));if(!fact){endpointRequests.push(row.descriptor);throw Error('source_instance_endpoint_facts_pending');}sourceEndpointMap.set(el,fact);} """
 assert code.count(oldlookup)==1
 code=code.replace(oldlookup,newlookup)
 assert code.count('return {objects,issues,nodes,sourceText:')==1
 code=code.replace('return {objects,issues,nodes,sourceText:', 'return {sourceEndpointRequests:endpointRequests,objects,issues,nodes,sourceText:')
 (S/new).write_text(code)
