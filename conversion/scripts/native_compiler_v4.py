"""Original native source -> portable fonts -> complete upstream tight export."""
from pathlib import Path
from native_html_compiler_v2 import repair_fonts
from native_export_reference_v4 import repair as export_repair
VERSION='original_native_font_and_complete_paint_export_v4'
def repair(record,job,work):
 if record.get('source_format')!='drawio':return {'ok':False,'reason':'native_v4_original_drawio_required'}
 result=repair_fonts(record,job,Path(work)/'fonts')
 if not result.get('ok'):return result
 exported=export_repair(result['record'],job,Path(work)/'export')
 if not exported.get('ok'):return {**result,'export_refusal':exported}
 return {**result,'record':exported['record'],'export_evidence':exported['evidence'],'version':VERSION}
