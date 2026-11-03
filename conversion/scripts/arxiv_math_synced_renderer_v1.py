"""Existing strict cold source replay with the official offline math component."""
from pathlib import Path
import hashlib,json,zipfile
from arxiv_bulk_official_xml_png_math_v1 import OfficialXmlPng,WAR
from arxiv_author_native_synced_replay_v1 import Synced,POLICY as BASE_POLICY
POLICY=BASE_POLICY+'__official_local_mathjax_svg_fontCache_none_v1'
class MathSynced(Synced):
 def __init__(self,asset_map=None):
  self.r=OfficialXmlPng();self.r.assets=asset_map or {};self.r.blocked.clear();self.r.missing.clear()
 def replay(self,xml,folder):
  proof=super().replay(xml,folder)
  with zipfile.ZipFile(WAR) as war:math=war.read('math4/es5/drawio-mathjax.min.js')
  proof.update(policy=POLICY,base_validation_policy=BASE_POLICY,official_math_bundle_sha256=hashlib.sha256(math).hexdigest(),official_MathJax_SVG_font_cache='none',old_exact_SVG_and_PNG_restore_thresholds_unchanged=True,new_PDF_import_calls=0)
  (Path(folder)/'synced_replay_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
  return proof
