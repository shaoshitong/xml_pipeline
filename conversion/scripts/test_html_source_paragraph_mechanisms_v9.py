"""Actual Chromium source-cascade and exact Text-backend calibration controls."""
import json,unittest
from playwright.sync_api import sync_playwright
from html_source_text_node_binding_v9 import physical_fonts_for_object
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
class ActualChromium(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def test_unitless_typed_CSS_whole_run_and_actual_paint_negatives(self):
  page=self.browser.new_page(viewport={'width':600,'height':300});page.set_content('<body style="margin:0;padding:8px"><div id="source" style="width:500px;height:200px;font:23px Arial;line-height:1.3;white-space:pre;color:black">first line\nsecond line\nthird line\nfourth line</div>');page.evaluate('document.fonts.ready');normal=page.screenshot();baseline=page.evaluate('''()=>{const e=document.getElementById('source'),n=e.firstChild,range=()=>[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)].map(({segment,index})=>{const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();return[segment,b.x,b.y,b.width,b.height]});window.__fixtureOriginalRanges=range();window.__fixtureRange=range;const lh=e.computedStyleMap().get('line-height');window.__fixtureStyle={fontSize:getComputedStyle(e).fontSize,lineHeightPx:getComputedStyle(e).lineHeight,typedValue:lh.value,typedUnit:lh.unit};return __fixtureStyle;}''');self.assertEqual(baseline['typedUnit'],'number');self.assertEqual(page.screenshot(),normal)
  def overlay(mode,mutation=None):
   return page.evaluate('''({mode,mutation})=>{window.__fixtureClone?.remove();const src=document.getElementById('source'),c=src.cloneNode(true);c.removeAttribute('id');c.style.position='absolute';c.style.left='8px';c.style.top='8px';c.style.color='black';c.style.lineHeight=mode==='typed'?String(__fixtureStyle.typedValue):__fixtureStyle.lineHeightPx;src.style.color='transparent';document.body.append(c);window.__fixtureClone=c;
    if(mutation==='missing')c.firstChild.deleteData(0,1);if(mutation==='font')c.style.fontFamily='Courier New';if(mutation==='color'){c.style.color='red';c.style.webkitTextFillColor='red';}if(mutation==='spacing')c.style.letterSpacing='1px';if(mutation==='move')c.style.top='9px';
    const n=c.firstChild,chars=[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)].map(({segment,index})=>{const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();return[segment,b.x,b.y,b.width,b.height]});return{chars,original:__fixtureOriginalRanges,sourceRangesUnchanged:JSON.stringify(__fixtureRange())===JSON.stringify(__fixtureOriginalRanges)};}''',{'mode':mode,'mutation':mutation})
  old=overlay('used-px');self.assertTrue(old['sourceRangesUnchanged']);res=max(abs(a-b)for x,y in zip(old['chars'],old['original'])for a,b in zip(x[1:],y[1:]));self.assertGreater(res,.03)
  exact=overlay('typed');self.assertEqual(exact['chars'],exact['original']);self.assertEqual(page.screenshot(),normal)
  for mutation in('missing','font','color','spacing','move'):
   obs=overlay('typed',mutation);self.assertTrue(obs['sourceRangesUnchanged']);self.assertNotEqual(page.screenshot(),normal,mutation)
  page.evaluate("()=>{__fixtureClone.remove();document.getElementById('source').style.color='black'}");self.assertEqual(page.screenshot(),normal);page.close()
 def test_actual_adjacent_repeated_Text_whitespace_and_wrong_indices(self):
  page=self.browser.new_page(viewport={'width':600,'height':200});page.set_content('<body><div id="host" style="white-space:pre;font:23px Arial"></div></body>');page.evaluate('''()=>{const h=document.getElementById('host');for(const n of [document.createTextNode('DUP'),document.createTextNode(' '),document.createComment('index witness'),document.createTextNode('DUP'),document.createTextNode(String.fromCharCode(10))])h.append(n);const s=document.createElement('span');s.style.fontFamily='Courier New';s.append(document.createTextNode('DUP'));h.append(s);window.__fixtureTextNodes=[h.childNodes[0],h.childNodes[1],h.childNodes[3],h.childNodes[4],s.firstChild];}''');page.evaluate('document.fonts.ready');normal=page.screenshot();s=page.context.new_cdp_session(page);s.send('DOM.enable',{'includeWhitespace':'all'});s.send('CSS.enable');doc=s.send('DOM.getDocument',{'depth':-1})['root']['nodeId'];parent=s.send('DOM.querySelector',{'nodeId':doc,'selector':'#host'})['nodeId'];results=[];objects=[]
  try:
   for i,index in enumerate([0,1,3,4]):
    obj=s.send('Runtime.evaluate',{'expression':'window.__fixtureTextNodes['+str(i)+']','returnByValue':False})['result']['objectId'];objects.append(obj);text=page.evaluate('i=>__fixtureTextNodes[i].textContent',i);fonts,binding=physical_fonts_for_object(s,obj,parent,index,text);results.append((fonts,binding))
   self.assertEqual(len({b['backendNodeId']for _,b in results}),4)
   with self.assertRaisesRegex(ValueError,'exact_original_parent_child_backend'):physical_fonts_for_object(s,objects[2],parent,0,'DUP')
   with self.assertRaisesRegex(ValueError,'exact_original_parent_child_backend'):physical_fonts_for_object(s,objects[1],parent,0,' ')
   with self.assertRaisesRegex(ValueError,'exact_original_parent_child_backend'):physical_fonts_for_object(s,objects[0],parent,2,'DUP')
   span=s.send('DOM.querySelector',{'nodeId':doc,'selector':'#host span'})['nodeId'];obj=s.send('Runtime.evaluate',{'expression':'__fixtureTextNodes[4]','returnByValue':False})['result']['objectId'];objects.append(obj);fonts,binding=physical_fonts_for_object(s,obj,span,0,'DUP');self.assertNotEqual({f['postScriptName']for f in fonts},{f['postScriptName']for f in results[0][0]})
   self.assertEqual(page.screenshot(),normal)
  finally:
   for obj in objects:s.send('Runtime.releaseObject',{'objectId':obj})
   s.detach();page.close()
if __name__=='__main__':unittest.main()
