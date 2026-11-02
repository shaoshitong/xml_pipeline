"""Actual upstream Graph text editing and byte-exact model/paint restoration."""
import hashlib,json,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')

def audit(xml,work):
 from portable_native_fonts import ready_page
 from playwright.sync_api import sync_playwright
 from fixed_batch_case_v1 import save,raw
 work=Path(work);work.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=ready_page(browser)
   setup=page.evaluate('''async xml=>{document.body.style.cssText='margin:0;background:white;';const d=mxUtils.parseXml(xml),m=d.getElementsByTagName('mxGraphModel')[0];for(const item of (m.getAttribute('extFonts')||'').split('|')){if(!item)continue;const i=item.indexOf('^'),family=item.slice(0,i),uri=item.slice(i+1);const f=new FontFace(family,'url("'+uri+'")');await f.load();document.fonts.add(f);}const e=document.createElement('div');e.style.cssText='position:absolute;left:0;top:0;width:'+m.getAttribute('pageWidth')+'px;height:'+m.getAttribute('pageHeight')+'px;';document.body.append(e);const g=new Graph(e);new mxCodec(d).decode(m,g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();window.__htmlEditV5=g;const cells=Object.values(g.model.cells).filter(c=>c.vertex&&g.getCellStyle(c).shape==='text'&&String(g.getLabel(c)||'').length>20&&g.view.getState(c)?.text?.node);if(!cells.length)throw Error('No actual editable text object');const c=cells[0];if(!g.isCellEditable(c))throw Error('Native text edit disabled');window.__htmlEditCellV5=c;window.__htmlEditOldV5=c.value;window.__htmlEditModelV5=mxUtils.getXml(new mxCodec().encode(g.model));return {cell:c.id,canvas:[+m.getAttribute('pageWidth'),+m.getAttribute('pageHeight')],label:String(g.getLabel(c))};}''',xml)
   page.set_viewport_size(dict(zip(['width','height'],setup['canvas'])));before=page.screenshot()
   changed=page.evaluate('''()=>{const g=__htmlEditV5,c=__htmlEditCellV5;g.model.setValue(c,'<span style="color:#ff0000;font-size:19px">QACONTROL editable native text</span>');g.refresh();g.view.validate();return {value_changed:c.value!==__htmlEditOldV5,actual_label: g.view.getState(c).text.node.textContent};}''');after=page.screenshot()
   restored=page.evaluate('''()=>{const g=__htmlEditV5,c=__htmlEditCellV5;g.model.setValue(c,__htmlEditOldV5);g.refresh();g.view.validate();return {model_restored:mxUtils.getXml(new mxCodec().encode(g.model))===__htmlEditModelV5,label_restored:c.value===__htmlEditOldV5};}''');final=page.screenshot()
   assert changed['value_changed'] and 'QACONTROL' in changed['actual_label'] and before!=after,'native_text_edit_did_not_change_actual_paint'
   assert restored['model_restored'] and restored['label_restored'] and before==final,'native_text_edit_did_not_restore_model_and_paint'
  finally:browser.close()
 for name,png in [('before',before),('edited',after),('restored',final)]:save(work/(name+'.png'),png)
 result=dict(ok=True,endpoint_moves=0,actual_native_text_edits=1,cell=setup['cell'],whole_encoded_model_restored=True,actual_native_png_restored_exactly=True,before_png_sha256=hashlib.sha256(before).hexdigest(),edited_png_sha256=hashlib.sha256(after).hexdigest(),profile='actual_upstream_Graph_native_text_edit_and_exact_restore_v5')
 save(work/'report.json',raw(result));return result
