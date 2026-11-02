"""Preregistered finite actual-factory calibration, no dataset or model calls."""
import argparse,hashlib,io,itertools,json,math,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
ROOT=W/'plantuml_closed_paint_calibration_v2';CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'

def raw(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()

def prepare():
 from native_worker import native
 from plantuml_marker_grid_rule_v1 import POLICY
 root=ROOT;root.mkdir(parents=True,exist_ok=True);plan=root/'preregistered_plan.json'
 files=[Path(__file__).resolve(),W/'scripts/plantuml_marker_grid_rule_v1.py',W/'scripts/plantuml_marker_closed_paint_v1.py',W/'scripts/plantuml_marker_minimax_v1.py',W/'scripts/compiler_plantuml_native_paint_quality_v1.py',W/'scripts/tikz_execution_binding_v2.py',W/'scripts/tikz_execution_marker_quality.py',native.renderer_path(R).parent/'assets/viewer-static.min.js',Path(CHROME)]
 spec={'schema':'plantuml_closed_paint_calibration_plan_v2','policy':POLICY,'depths':[7.,9.,12.],'stroke_widths':[1.,1.5,2.],'kinds':['classic','classicThin'],'angles_degrees':[0,17,37,67,90,123,151,211],'phases':[[0,0],[.2,.7],[.5,.5],[.9,.1]],'known_valid_translation_magnitudes':[0.,.5,.85],'negative_base_stride':27,'negative_variants':['physical_translation_1.25px','depth_scale_1.4','reversed_direction','removed_fill'],'template_notch_depths':[4.997,5.003],'template_depth':9.,'template_width':8.,'template_stroke':1.,'positive_translation_cases':1728,'template_cases':64,'negative_cases':256,'unsupported_stroke_cases':576,'total_cases':2624,'previous_failed_plan_sha256':'6042a650febeab1cd11cfb7a5634d576bd51ff340a7b10f0450ac4431c025e72','fixture_correction':'Retain all subpixel 0.5px inputs as negative source/native paint-style mismatch controls because the actual native canvas clamps them to 1px; add supported 2px positive stroke. No physical/raster/area thresholds changed.','batch_size':64,'tile_size':80,'columns':8,'physical_boundary_limit_px':1.,'raster_grid_cap_px':math.sqrt(2),'ink_area_interval':[.8,1.25],'pass_conditions':{'known_translation_geometry_certificates_all':True,'known_translation_rule_acceptance_min_fraction':.8,'template_geometry_certificates_all':True,'actual_negative_false_acceptances':0,'minimum_actual_alias_acceptances':10,'actual_factory_geometry_parity_max_px':.03},'source_style':{'fill':'#181818','stroke':'#181818','linejoin':'miter','miterlimit':4,'opacity':1},'pins':{str(p):sha(p.read_bytes()) for p in files},'model_calls':0,'dataset_samples_consumed':0,'no_gate_changes_after_observation':True}
 with plan.open('xb') as stream:stream.write(raw(spec))
 print(json.dumps({'plan':str(plan),'sha256':sha(plan.read_bytes()),'cases':2624}),flush=True)

def check(plan):
 for name,digest in plan['pins'].items():
  if sha(Path(name).read_bytes())!=digest:raise ValueError('calibration_pin_changed:'+name)

def cases(plan):
 from tikz_execution_binding_v2 import native_marker_polygon
 from plantuml_marker_minimax_v1 import classic
 rows=[]
 for kind,depth,stroke,angle,phase,magnitude in itertools.product(plan['kinds'],plan['depths'],plan['stroke_widths'],plan['angles_degrees'],plan['phases'],plan['known_valid_translation_magnitudes']):
  theta=math.radians(angle);u=(math.cos(theta),math.sin(theta));pe=(40+phase[0],40+phase[1]);poly,_=native_marker_polygon(kind,depth-stroke,stroke,pe,u);shift=(-u[1]*magnitude,u[0]*magnitude);source=[(x+shift[0],y+shift[1]) for x,y in poly];rows.append({'category':'known_translation','kind':kind,'depth':depth,'stroke':stroke,'angle':angle,'phase':phase,'native_point':pe,'native_unit':u,'source_polygon':source,'filled':True,'source_known_valid_translation_px':magnitude})
 originals=list(rows)
 for index,row in enumerate(originals):
  if index%plan['negative_base_stride']:continue
  source,_=native_marker_polygon(row['kind'],row['depth']-row['stroke'],row['stroke'],row['native_point'],row['native_unit'])
  for name in plan['negative_variants']:
   item={**row,'category':'negative','mutation':name,'source_polygon':source}
   if name=='physical_translation_1.25px':item['native_point']=tuple(row['native_point'][i]+1.25*row['native_unit'][i] for i in (0,1))
   elif name=='depth_scale_1.4':item['depth']=row['depth']*1.4
   elif name=='reversed_direction':item['native_unit']=tuple(-v for v in row['native_unit'])
   elif name=='removed_fill':item['filled']=False
   rows.append(item)
 for notch in plan['template_notch_depths']:
  obj={'pointsAttr':f'0,0 -9,4 -{notch},0 -9,-4','matrix':[1,0,0,1,0,0],'original_computed_paint':{'strokeWidth':1,'linejoin':'miter','miterlimit':4}};fit=classic(obj,[[-20,0],[0,0]],'end')
  if fit is None:raise ValueError('preregistered_source_template_has_no_certified_proposal')
  for angle,phase in itertools.product(plan['angles_degrees'],plan['phases']):
   theta=math.radians(angle);u=(math.cos(theta),math.sin(theta));v=(-u[1],u[0]);tip=(40+phase[0],40+phase[1]);source=[(tip[0]+x*u[0]+y*v[0],tip[1]+x*u[1]+y*v[1]) for x,y in [(0,0),(-9,4),(-notch,0),(-9,-4)]];pe=tuple(tip[i]+(fit['tip'][0]+1.118)*u[i]+fit['tip'][1]*v[i] for i in (0,1));rows.append({'category':'plantuml_template','kind':fit['arrow'],'depth':fit['length'],'stroke':1.,'angle':angle,'phase':phase,'native_point':pe,'native_unit':u,'source_polygon':source,'filled':True,'source_notch_depth':notch})
 for kind,depth,angle,phase,magnitude in itertools.product(plan['kinds'],plan['depths'],plan['angles_degrees'],plan['phases'],plan['known_valid_translation_magnitudes']):
  stroke=.5;theta=math.radians(angle);u=(math.cos(theta),math.sin(theta));pe=(40+phase[0],40+phase[1]);poly,_=native_marker_polygon(kind,depth-stroke,stroke,pe,u);shift=(-u[1]*magnitude,u[0]*magnitude);source=[(x+shift[0],y+shift[1]) for x,y in poly];rows.append({'category':'unsupported_stroke','mutation':'actual_native_minimum_width_mismatch','kind':kind,'depth':depth,'stroke':stroke,'angle':angle,'phase':phase,'native_point':pe,'native_unit':u,'source_polygon':source,'filled':True})
 for index,row in enumerate(rows):row['index']=index
 if len(rows)!=plan['total_cases']:raise ValueError('calibration_case_count_changed')
 return rows

DRAW=r'''rows=>{const NS='http://www.w3.org/2000/svg';document.body.style.margin='0';document.body.style.background='white';document.body.innerHTML='';function element(tag,attrs){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;}const source=element('svg',{width:640,height:640,style:'position:absolute;left:0;top:0'}),native=element('svg',{width:640,height:640,style:'position:absolute;left:640px;top:0'});document.body.append(source,native);const results=[];for(let i=0;i<rows.length;i++){const row=rows[i],x=(i%8)*80,y=Math.floor(i/8)*80,sg=element('g',{transform:'translate('+x+','+y+')'}),ng=element('g',{transform:'translate('+x+','+y+')'});source.appendChild(sg);native.appendChild(ng);const polygon=element('polygon',{points:row.source_polygon.map(p=>p.join(',')).join(' '),fill:'#181818',stroke:'#181818','stroke-width':row.stroke,'stroke-linejoin':'miter','stroke-miterlimit':4});sg.appendChild(polygon);const canvas=new mxSvgCanvas2D(ng);canvas.setStrokeColor('#181818');canvas.setFillColor('#181818');canvas.setStrokeWidth(row.stroke);canvas.setLineJoin('miter');canvas.setMiterLimit(4);const pe=new mxPoint(...row.native_point),draw=mxMarker.createMarker(canvas,{},row.kind,pe,...row.native_unit,row.depth-row.stroke,false,row.stroke,row.filled);if(!draw)throw Error('actual_native_factory_missing');draw();const paths=[...ng.querySelectorAll('path')];if(paths.length!==1)throw Error('actual_native_factory_paint_scope_changed');const path=paths[0];function css(e){const c=getComputedStyle(e);return {fill:c.fill,stroke:c.stroke,strokeWidth:parseFloat(c.strokeWidth),linejoin:c.strokeLinejoin,miterlimit:parseFloat(c.strokeMiterlimit),opacity:+c.opacity,fillOpacity:+c.fillOpacity,strokeOpacity:+c.strokeOpacity};}results.push({index:row.index,source_polygon:[...polygon.points].map(p=>[p.x,p.y]),actual_native_path:path.getAttribute('d'),source_style:css(polygon),native_style:css(path),actual_factory_executed:true});}return results;}'''

def run():
 import numpy as np
 from PIL import Image
 from scipy.ndimage import binary_erosion,distance_transform_edt
 from playwright.sync_api import sync_playwright
 from native_worker import native
 from tikz_execution_binding_v2 import native_marker_polygon
 from tikz_execution_marker_quality import _mask,_color
 from plantuml_marker_closed_paint_v1 import outline,certificate
 from compiler_plantuml_native_paint_quality_v1 import native_polygon
 from plantuml_marker_grid_rule_v1 import decision
 plan_path=ROOT/'preregistered_plan.json';plan=json.loads(plan_path.read_text());check(plan);inputs=cases(plan);owner=ROOT/'runs'/uuid.uuid4().hex;owner.mkdir(parents=True);(owner/'inputs.json').write_bytes(raw(inputs));results=[];runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js'
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=browser.new_page(viewport={'width':1280,'height':640},device_scale_factor=1);page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(runtime))
   for offset in range(0,len(inputs),plan['batch_size']):
    chunk=inputs[offset:offset+plan['batch_size']];observed=page.evaluate(DRAW,chunk);png=page.screenshot();image=np.asarray(Image.open(io.BytesIO(png)).convert('RGB'));(owner/f'batch_{offset:04d}.png').write_bytes(png)
    for index,(source,actual) in enumerate(zip(chunk,observed)):
     x=(index%8)*80;y=(index//8)*80;a=_mask(image[y:y+80,x:x+80],_color('#181818'));b=_mask(image[y:y+80,640+x:640+x+80],_color('#181818'));distance=None;ratio=float(b.sum()/max(1,a.sum()))
     if a.any() and b.any():
      aa=a&~binary_erosion(a,structure=np.ones((3,3)),border_value=0);bb=b&~binary_erosion(b,structure=np.ones((3,3)),border_value=0);distance=float(max(distance_transform_edt(~bb)[aa].max(),distance_transform_edt(~aa)[bb].max()))
     points=native_polygon({'d':actual['actual_native_path'],'transform':None},0);ss=actual['source_style'];ns=actual['native_style'];style=all(ss[k]==ns[k] for k in ('fill','stroke','strokeWidth','linejoin','miterlimit','opacity','fillOpacity','strokeOpacity'))
     closed=certificate(outline(actual['source_polygon'],ss['strokeWidth'],ss['linejoin'],ss['miterlimit']),outline(points,ns['strokeWidth'],ns['linejoin'],ns['miterlimit'])) if style else {'ok':False,'both_full_closed_paint_boundaries':False,'reason':'actual_paint_style_or_opaque_fill_topology_changed_not_certified'}
     predicted,_=native_marker_polygon(source['kind'],source['depth']-source['stroke'],source['stroke'],source['native_point'],source['native_unit']);parity=max(max(min(math.dist(p,q) for q in predicted) for p in points),max(min(math.dist(p,q) for q in points) for p in predicted));result=decision(distance,ratio,closed,opaque_paint_style_equivalent=style);results.append({'index':source['index'],'category':source['category'],'mutation':source.get('mutation'),'actual_native_factory_executed':actual['actual_factory_executed'],'source_style':ss,'actual_native_style':ns,'source_DOM_polygon':actual['source_polygon'],'actual_native_path':actual['actual_native_path'],'actual_factory_geometry_max_vertex_error_px':parity,'source_native_style_equivalent':style,'raster_boundary_distance_px':distance,'ink_area_ratio':ratio,'full_paint_certificate':closed,**result})
    (owner/'progress.json').write_bytes(raw({'completed':len(results),'total':len(inputs)}));print(json.dumps({'completed':len(results),'total':len(inputs)}),flush=True)
  finally:browser.close()
 check(plan);positives=[r for r in results if r['category']=='known_translation'];templates=[r for r in results if r['category']=='plantuml_template'];negatives=[r for r in results if r['category']=='negative'];unsupported=[r for r in results if r['category']=='unsupported_stroke'];false_accepts=sum(r['ok'] for r in negatives+unsupported);aliases=sum(r['grid_alias_used'] for r in positives+templates);positive_rate=sum(r['ok'] for r in positives)/len(positives);conditions=plan['pass_conditions'];passed=all(r['full_paint_certificate']['ok'] for r in positives+templates) and positive_rate>=conditions['known_translation_rule_acceptance_min_fraction'] and false_accepts==0 and aliases>=conditions['minimum_actual_alias_acceptances'] and max(r['actual_factory_geometry_max_vertex_error_px'] for r in results)<=conditions['actual_factory_geometry_parity_max_px']
 report={'schema':'plantuml_closed_paint_calibration_report_v2','plan_sha256':sha(plan_path.read_bytes()),'plan':str(plan_path),'policy':plan['policy'],'passed':passed,'total_cases':len(results),'positive_translation_cases':len(positives),'template_cases':len(templates),'negative_cases':len(negatives),'unsupported_stroke_cases':len(unsupported),'known_translation_rule_acceptance_fraction':positive_rate,'actual_negative_false_acceptances':false_accepts,'actual_alias_acceptances':aliases,'known_positive_full_paint_certificates':sum(r['full_paint_certificate']['ok'] for r in positives),'template_full_paint_certificates':sum(r['full_paint_certificate']['ok'] for r in templates),'actual_factory_parity_max_error_px':max(r['actual_factory_geometry_max_vertex_error_px'] for r in results),'results':results,'model_calls':0,'dataset_samples_consumed':0,'inputs':{'file':str(owner/'inputs.json'),'sha256':sha((owner/'inputs.json').read_bytes())},'output':str(owner/'report.json')};(owner/'report.json').write_bytes(raw(report));print(json.dumps({k:v for k,v in report.items() if k!='results'}),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();prepare() if args.action=='prepare' else run()
