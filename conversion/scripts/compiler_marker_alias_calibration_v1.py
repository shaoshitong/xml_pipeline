"""Finite preregistered actual-native/source-SVG marker pixel-grid calibration."""
import pathlib,sys,json,math,hashlib,itertools,io,copy,xml.etree.ElementTree as ET
R=pathlib.Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'));sys.path.append(str(W/'prototype'))
import native_marker_geometry_exact_v1 as rule
from native_svg_screen_offset_v1 import transform
from compiler_svg_source_layout_v4 import _screenshot
from portable_native_fonts import ready_page
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np
from scipy.ndimage import binary_erosion,distance_transform_edt
from tikz_execution_marker_quality import _mask,_color
owner=W/'native_marker_exact_grid_calibration_v1';owner.mkdir(exist_ok=False)
canon=lambda x:(json.dumps(x,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode();sha=lambda b:hashlib.sha256(b).hexdigest()
plan={'policy':rule.POLICY,'geometry_epsilon_px':1e-6,'nonexact_boundary_px':1,'exact_geometry_only_boundary_px':math.sqrt(2),'area_interval':[.8,1.25],'depths':[6,13.5,24],'ratios':{'block':1,'blockThin':2/3},'stroke_widths':[1,1.5],'angles':[0,30,45,90,135,180,225,270],'phases':[[0,0],[.25,.5]],'marker_viewport':'hidden and whole filled triangle geometrically contained','negative_subset':'phase index equals parity(depth_index+kind_index+stroke_index+angle_index)','negative_variants':['offset_x_0.01px','offset_x_0.02px','head_depth_plus_0.02px','reverse_direction'],'requires_zero_effective_negative_alias_acceptances':True,'all_other_real_data_gates_unchanged':True,'no_dataset_samples':True,'script_sha256':sha(pathlib.Path(__file__).read_bytes()),'rule_sha256':sha(pathlib.Path(rule.__file__).read_bytes())};(owner/'preregistered_plan.json').write_bytes(canon(plan));print(json.dumps({'preregistered_plan':str(owner/'preregistered_plan.json'),'sha256':sha((owner/'preregistered_plan.json').read_bytes())}),flush=True)

def inputs(depth,ratio,stroke,angle,phase,kind):
 angle=math.radians(angle);u=(math.cos(angle),math.sin(angle));tip=(128+phase[0]+40*u[0],128+phase[1]+40*u[1]);start=(tip[0]-80*u[0],tip[1]-80*u[1]);width=depth*ratio;points=[tip,(tip[0]-depth*u[0]-width*u[1]/2,tip[1]-depth*u[1]+width*u[0]/2),(tip[0]-depth*u[0]+width*u[1]/2,tip[1]-depth*u[1]-width*u[0]/2)];nominal_depth=depth/stroke;nominal_width=width/stroke
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><defs><marker id="head" markerUnits="strokeWidth" markerWidth="{nominal_depth}" markerHeight="{nominal_width}" refX="{nominal_depth}" refY="{nominal_width/2}" orient="auto" overflow="hidden"><polygon points="{nominal_depth},{nominal_width/2} 0,0 0,{nominal_width}" fill="black" stroke="none"/></marker></defs><path d="M{start[0]},{start[1]} L{tip[0]},{tip[1]}" stroke="black" stroke-width="{stroke}" fill="none" marker-end="url(#head)"/></svg>'
 root=ET.Element('mxfile');model=ET.SubElement(ET.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='256',pageHeight='256');container=ET.SubElement(model,'root');ET.SubElement(container,'mxCell',id='0');ET.SubElement(container,'mxCell',id='1',parent='0')
 for key,p in [('s',start),('t',tip)]:
  cell=ET.SubElement(container,'mxCell',id=key,parent='1',vertex='1',style='fillColor=none;strokeColor=none;');ET.SubElement(cell,'mxGeometry',x=str(p[0]-1),y=str(p[1]-1),width='2',height='2',attrib={'as':'geometry'})
 endpoint=(tip[0]+u[0]*stroke*1.118,tip[1]+u[1]*stroke*1.118);style={'strokeColor':'#000000','strokeWidth':stroke,'fillColor':'none','startArrow':'none','endArrow':kind,'endSize':depth-stroke,'endFill':'1','endFillColor':'#000000','endStrokeColor':'transparent','edgeStyle':'none','exitX':.5,'exitY':.5,'exitPerimeter':0,'entryX':(endpoint[0]-tip[0]+1)/2,'entryY':(endpoint[1]-tip[1]+1)/2,'entryPerimeter':0};edge=ET.SubElement(container,'mxCell',id='e',parent='1',edge='1',source='s',target='t',style=';'.join(k+'='+str(v) for k,v in style.items())+';');ET.SubElement(edge,'mxGeometry',relative='1',attrib={'as':'geometry'});offset=.5 if max(1,math.floor(stroke+.5))%2 else 0;xml=transform(ET.tostring(root,encoding='unicode'),{'e':offset},-1)
 return svg,xml,points,offset

def geometry(calls,points):
 selected=[c for c in calls if c['edge']=='e' and c['side']=='end']
 if not selected:return {'exact_geometry':False,'source_fill_and_absent_stroke_match':False,'reason':'actual_expected_end_marker_missing'}
 return rule.compare_paint(selected[-1]['paint'],selected[-1]['offset'],points,'#000000')

def contour(source,native,points):
 s=np.asarray(Image.open(io.BytesIO(source)).convert('RGB'));n=np.asarray(Image.open(io.BytesIO(native)).convert('RGB'));x0=max(0,math.floor(min(p[0] for p in points))-3);y0=max(0,math.floor(min(p[1] for p in points))-3);x1=min(256,math.ceil(max(p[0] for p in points))+3);y1=min(256,math.ceil(max(p[1] for p in points))+3);a=_mask(s[y0:y1,x0:x1],_color('rgb(0,0,0)'));b=_mask(n[y0:y1,x0:x1],_color('rgb(0,0,0)'));aa=a&~binary_erosion(a,structure=np.ones((3,3)),border_value=0);bb=b&~binary_erosion(b,structure=np.ones((3,3)),border_value=0);distance=float(max(distance_transform_edt(~bb)[aa].max(),distance_transform_edt(~aa)[bb].max()));return distance,float(b.sum()/a.sum())

positives=[];negatives=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);page=ready_page(browser);page.set_viewport_size({'width':256,'height':256});page.add_style_tag(content='html,body{margin:0;padding:0;background:white}svg{display:block}')
 try:
  for li,depth in enumerate(plan['depths']):
   for ki,(kind,ratio) in enumerate(plan['ratios'].items()):
    for si,stroke in enumerate(plan['stroke_widths']):
     for ai,angle in enumerate(plan['angles']):
      for pi,phase in enumerate(plan['phases']):
       svg,xml,points,offset=inputs(depth,ratio,stroke,angle,phase,kind);page.evaluate("s=>{if(window.calibrationGraph){window.calibrationGraph.destroy();delete window.calibrationGraph;}document.body.innerHTML='<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+s}",svg);source=_screenshot(page);calls=page.evaluate(rule.OBSERVE_SCRIPT,{'xml':xml});native=_screenshot(page);proof=geometry(calls,points);dist,area=contour(source,native,points);decision=rule.contour_decision(dist,area,proof,source_viewport_containment=True,actual_editing=True);row={'depth':depth,'kind':kind,'stroke':stroke,'angle':angle,'phase':phase,'maximum_vertex_error_px':proof.get('maximum_vertex_error_px'),'exact_geometry':proof['exact_geometry'],'boundary_distance_px':dist,'ink_area_ratio':area,**decision};positives.append(row)
       if pi==(li+ki+si+ai)%2:
        for name in plan['negative_variants']:
         tree=ET.fromstring(xml);e=next(c for c in tree.iter('mxCell') if c.get('id')=='e');style=dict(v.split('=',1) for v in e.get('style').split(';') if '=' in v)
         if name.startswith('offset_x_'):delta=.01 if '0.01' in name else .02;style['entryX']=str(float(style['entryX'])+delta/2)
         elif name=='head_depth_plus_0.02px':style['endSize']=str(float(style['endSize'])+.02)
         else:style['startArrow']=style['endArrow'];style['startSize']=style['endSize'];style['endArrow']='none'
         e.set('style',';'.join(k+'='+v for k,v in style.items())+';');observed=page.evaluate(rule.OBSERVE_SCRIPT,{'xml':ET.tostring(tree,encoding='unicode')});g=geometry(observed,points);alias=rule.contour_decision(math.sqrt(2),1,g,source_viewport_containment=True,actual_editing=True);negatives.append({'mutation':name,'depth':depth,'kind':kind,'stroke':stroke,'angle':angle,'phase':phase,'maximum_actual_geometry_error_px':g.get('maximum_vertex_error_px'),'actual_geometry_exact':g['exact_geometry'],'alias_eligible':alias['exact_geometry_alias_eligible'],'alias_would_accept':alias['ok']})
       if len(positives)%32==0:print(json.dumps({'synthetic_positive_cases':len(positives),'negative_cases':len(negatives),'exact_geometry':sum(r['exact_geometry'] for r in positives),'alias_only':sum(r['alias_used'] for r in positives),'negative_alias_acceptances':sum(r['alias_would_accept'] for r in negatives)}),flush=True)
 finally:browser.close()
report={'policy':rule.POLICY,'plan_sha256':sha((owner/'preregistered_plan.json').read_bytes()),'positive_cases':len(positives),'old_rule_passed':sum(r['old_rule_passed'] for r in positives),'exact_geometry_cases':sum(r['exact_geometry'] for r in positives),'exact_alias_only_cases':sum(r['alias_used'] for r in positives),'new_rule_passed':sum(r['ok'] for r in positives),'negative_cases':len(negatives),'negative_alias_acceptances':sum(r['alias_would_accept'] for r in negatives),'positive_results':positives,'negative_results':negatives,'passed':bool(positives) and any(r['alias_used'] for r in positives) and not any(r['alias_would_accept'] for r in negatives),'new_original_ids':0,'model_calls':0,'all_cases_synthetic':True};(owner/'report.json').write_bytes(canon(report));print(json.dumps({k:v for k,v in report.items() if k not in ('positive_results','negative_results')}),flush=True)
