"""Finite nonpainting alphabetic-baseline measurement; never selects a repair."""
import hashlib,json
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
JS=W/'scripts/html_css_baseline_probe_v1.js'
sha=lambda b:hashlib.sha256(b).hexdigest()
def observe(page,screenshot,dom=None):
 script=JS.read_text();before=page.evaluate(script,dict(mode='begin',dom=dom));png0=screenshot();inserted=page.evaluate(script,dict(mode='insert',dom=None));png1=screenshot();restored=page.evaluate(script,dict(mode='restore',dom=None));png2=screenshot()
 rows=inserted['rows'];ranges=all(x['before']==x['after']for x in rows);exact=png0==png1==png2
 return {'schema':'nonpainting_CSS_alphabetic_baseline_marker_v1','ok':exact and ranges and restored['all_original_text_font_and_grapheme_ranges_exact'],'nodes':before['nodes'],'all_source_pixels_byte_identical':exact,'inserted_marker_preserves_all_original_ranges_and_fonts':ranges,'restored':restored,'before_png_sha256':sha(png0),'marker_png_sha256':sha(png1),'restored_png_sha256':sha(png2),'rows':rows,'probe_module_sha256':sha(Path(__file__).read_bytes()),'probe_JS_sha256':sha(JS.read_bytes()),'never_uses_reference_ink_to_select_offsets':True}
