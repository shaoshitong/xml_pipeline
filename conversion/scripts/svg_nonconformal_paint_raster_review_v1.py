"""Fixed 64x actual observed SVG stroke raster cross-sections; no emitter."""
from pathlib import Path
import sys,json,io,uuid,math,hashlib,html,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sha=lambda b:hashlib.sha256(b).hexdigest()
PROOF=W/'svg_nonconformal_qualified_review_v1/f08281229ed347a9a604635d61d97225/measurements/proof.json'
PROOF_SHA='e22fbdfe82e9a79748d0e5b53bec0d172c544c50d6a04b5e82dfbf52d1896b3e'
SCALE=64;CROSS_SECTION_VIEW=[-.25,-4,.5,8]

def panel(paint,world,tangent):
 # Every value is an original source/actual native DOM paint fact. A rigid
 # inspection rotation centers the original SOURCE witness, never image ink.
 length=math.hypot(*tangent);ux,uy=tangent[0]/length,tangent[1]/length
 rotation=[ux,-uy,uy,ux,-ux*world[0]-uy*world[1],uy*world[0]-ux*world[1]]
 root=E.Element('svg',xmlns='http://www.w3.org/2000/svg',width='32',height='512',viewBox='-.25 -4 .5 8');g=E.SubElement(root,'g',transform='matrix('+','.join(map(repr,rotation))+')');sub=E.SubElement(g,'g',transform='matrix('+','.join(map(repr,paint['matrix']))+')');E.SubElement(sub,'path',d=paint['d'],fill='none',stroke=paint['stroke'],attrib={'stroke-width':str(paint['strokeWidth']),'stroke-linecap':paint['strokeLinecap'],'stroke-linejoin':paint['strokeLinejoin'],'stroke-miterlimit':str(paint['strokeMiterlimit']),'stroke-opacity':str(paint['strokeOpacity']),'opacity':str(paint['opacity']),'vector-effect':paint['vectorEffect']});return E.tostring(root,encoding='unicode')

def child(work):
 from PIL import Image
 import numpy as np
 from playwright.sync_api import sync_playwright
 work=Path(work);work.mkdir(parents=True,exist_ok=False);assert sha(PROOF.read_bytes())==PROOF_SHA;previous=json.loads(PROOF.read_bytes());selected=[]
 for case in previous['cases']:
  seen=set()
  for obj in case['measurements']:
   source=obj['source'];key=(obj['native']['role'],source['tag'],source['computed']['strokeWidth'],tuple(source['matrix'][:4]))
   if key in seen:continue
   seen.add(key);selected.append((case['id'],obj))
 rows=[]
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);page=browser.new_page(viewport=dict(width=32,height=512),device_scale_factor=1)
  try:
   for identifier,obj in selected:
    values=[]
    for index,witness in enumerate(obj['cross_sections']):
     source={**obj['source']['computed'],'d':obj['source']['d'],'matrix':obj['source']['matrix']};native=next(p for p in obj['native']['paint']if p['tag']=='path');pair={}
     for role,paint in [('original_source_paint',source),('actual_native_paint',native)]:
      assert paint['vectorEffect']=='none'and paint['opacity']==paint['strokeOpacity']==1 and paint['strokeDasharray']=='none';code=panel(paint,witness['world_point'],witness['world_tangent']);page.set_content('<style>html,body{margin:0;padding:0;background:transparent}svg{display:block}</style>'+code);png=page.screenshot(omit_background=True,animations='disabled');a=np.asarray(Image.open(io.BytesIO(png)).convert('RGBA'))[:,:,3].astype(float)/255;columns=a.sum(axis=0)/SCALE;width=float(columns[14:18].mean());edge=(a[:2,:].sum()+a[-2:,:].sum());assert edge==0,'inspection_frame_crops_stroke';stem=identifier[:8]+'_'+obj['id']+'_'+str(index)+'_'+role;(work/(stem+'.svg')).write_text(code);(work/(stem+'.png')).write_bytes(png);pair[role]=dict(physical_alpha_integral_width_px=width,central_column_widths=columns[14:18].tolist(),actual_paint_snapshot_SVG_sha256=sha(code.encode()),actual_raster_PNG_sha256=sha(png),inspection_crop_contains_entire_stroke=True)
     values.append(dict(source_parameter=witness['source_parameter'],source_segment_degree=witness['source_segment_degree'],world_point=witness['world_point'],world_tangent=witness['world_tangent'],source_analytic_width=witness['source_analytic_transformed_normal_width'],measurements=pair,native_minus_source_width_px=pair['actual_native_paint']['physical_alpha_integral_width_px']-pair['original_source_paint']['physical_alpha_integral_width_px']))
    rows.append(dict(id=identifier,object=obj['id'],tag=obj['source']['tag'],role=obj['native']['role'],source_CTM=obj['source']['matrix'],actual_native_CTM=native['matrix'],actual_native_SVG_strokeWidth=native['strokeWidth'],samples=values))
  finally:browser.close()
 report=dict(schema='fixed_64x_actual_observed_SVG_stroke_raster_cross_section_v1',input_actual_DOM_measurement=dict(file=str(PROOF),sha256=PROOF_SHA),selection='first existing object in each original tag/native role/physical strokeWidth/actual linear CTM class',fixed_pixels_per_original_CSS_unit=SCALE,fixed_world_cross_section_viewbox=CROSS_SECTION_VIEW,alpha_integral_central_columns=[14,15,16,17],cases=rows,normal_frontend_calls=0,new_heldout=0,qualified_ledger_writes=0,source_reference_gate_changes=0,model_calls=0,diagnostic_only_not_new_acceptance_rule=True);p=work/'proof.json';p.write_text(json.dumps(report,indent=2));print(json.dumps(dict(file=str(p),sha256=sha(p.read_bytes()),classes=len(rows),sample_pairs=sum(len(row['samples'])for row in rows))))

def run():
 import initial_conversion_process_v1 as bounded
 work=W/'svg_nonconformal_paint_raster_review_v1'/uuid.uuid4().hex;result=bounded.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(work/'rasters')],work/'owned_child',120);work.mkdir(parents=True,exist_ok=True);(work/'receipt.json').write_text(json.dumps(dict(process=result,normal_frontend_calls=0,model_calls=0),indent=2));print(json.dumps(dict(receipt=str(work/'receipt.json'),ok=result['ok'],stdout=result['stdout_file'],stderr=result['stderr_file'],cleanup_complete=result['cleanup_complete'])))
if __name__=='__main__':child(sys.argv[2])if'--child'in sys.argv else run()
