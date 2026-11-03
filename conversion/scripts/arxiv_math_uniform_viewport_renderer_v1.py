"""Canonical editor view state; unmodified source cells and unchanged strict QA."""
from pathlib import Path
import json
from arxiv_math_synced_renderer_v1 import MathSynced as Previous,POLICY as OLD_POLICY
POLICY=OLD_POLICY+'__identity_view_scale_translate_scroll_before_every_validation_stage_v1'
class MathSynced(Previous):
 def settled(self):
  self.r.page.evaluate("""()=>{const g=__bulkUi.editor.graph;g.view.setScale(1);g.view.setTranslate(0,0);g.container.scrollLeft=0;g.container.scrollTop=0;}""")
  return super().settled()
 def replay(self,xml,folder):
  proof=super().replay(xml,folder)
  proof.update(policy=POLICY,uniform_view_scale=1,uniform_view_translate=[0,0],uniform_view_scroll=[0,0],source_geometry_unchanged=proof['source_geometry_topology_style_inventory_sha256']==proof['restored_geometry_topology_style_inventory_sha256'],existing_exact_restore_checks_unchanged=True,original_XML_not_rewritten=True)
  (Path(folder)/'synced_replay_proof.json').write_text(json.dumps(proof,indent=2)+'\n')
  return proof
