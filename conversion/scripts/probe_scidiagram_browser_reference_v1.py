from pathlib import Path
import hashlib,json,sys,sqlite3,time,traceback,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def main():
 import compiler_scidiagram_source_frontend_v1 as f
 from scidiagram_panel_assets_v1 import inventory,resolve
 import compiler_render_domain_v3 as domain
 from auto_quality_common import image_quality
 work=R/'conversion/scidiagram_browser_reference_probe_v1'/uuid.uuid4().hex;work.mkdir(parents=True);identifier='0186e98ef75dda6a66308b68b0fc72be864a3e197416d82fae0134eba19d3d10';result=dict(id=identifier,work=str(work),normal_calls=0,QA_calls=0,accepted=False);t=time.monotonic()
 try:
  ctx=inventory(dict(id=identifier));m=ctx['manifest'];code=(R/m['source_code']).read_bytes();resolved,assets=resolve(code,ctx);ref=(R/m['reference_image']).read_bytes();size=(m['width'],m['height']);capture=f._BASE_CAPTURE(resolved,size,work,cairo_fonts=None);positions=domain._positions(capture['positions'],(0,0));comparison=image_quality(ref,capture['png'],{},positions);result.update(source_browser_reference=comparison,source_objects=len(capture['dom']['objects']),source_physical_faces=len(capture['faces']),original_code_sha256=hashlib.sha256(code).hexdigest(),asset_resolution=assets);(work/'original_reference.png').write_bytes(ref)
 except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
 result['elapsed_seconds']=time.monotonic()-t;(work/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
