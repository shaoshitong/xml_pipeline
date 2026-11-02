import unittest,copy,xml.etree.ElementTree as E
from plantuml_engine_shadow_source_v1 import specs,native_style,KEYS,PARAMS
XML='''<svg xmlns="http://www.w3.org/2000/svg"><defs><filter id="f0" x="-1" y="-1" width="300%" height="300%"><feGaussianBlur result="blurOut" stdDeviation="2"/><feColorMatrix in="blurOut" result="blurOut2" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .4 0"/><feOffset dx="4" dy="4" in="blurOut2" result="blurOut3"/><feBlend in="SourceGraphic" in2="blurOut3" mode="normal"/></filter></defs></svg>'''
class SourceEffect(unittest.TestCase):
 def test_complete_operators(self):self.assertTrue(specs(XML)['f0']['supported'])
 def bad(self,index,key,value):
  r=E.fromstring(XML);f=next(e for e in r.iter()if e.tag.endswith('}filter'));n=f if index is None else list(f)[index];n.set(key,value);self.assertFalse(specs(E.tostring(r))['f0']['supported'])
 def test_sigma_not_two(self):self.bad(0,'stdDeviation','3')
 def test_alpha_not_pointfour(self):self.bad(1,'values','0 '*18+'.5 0')
 def test_offset_x(self):self.bad(2,'dx','5')
 def test_offset_y(self):self.bad(2,'dy','-4')
 def test_wrong_blend(self):self.bad(3,'mode','multiply')
 def test_wrong_input(self):self.bad(0,'in','BackgroundImage')
 def test_wrong_binding(self):self.bad(1,'in','unknown')
 def test_color_interpolation(self):self.bad(None,'color-interpolation-filters','sRGB')
 def test_different_filter_region(self):self.bad(None,'width','200%')
 def test_different_filter_units(self):self.bad(None,'filterUnits','userSpaceOnUse')
 def test_undeclared_operator_parameter(self):self.bad(2,'href','https://invalid.example/')
 def test_native_exact(self):self.assertTrue(native_style(KEYS,dict(supported=True,params=PARAMS)))
 def test_native_sigma(self):
  with self.assertRaises(ValueError):native_style(dict(KEYS,shadowBlur='3'),dict(supported=True,params=PARAMS))
 def test_native_alpha(self):
  with self.assertRaises(ValueError):native_style(dict(KEYS,shadowOpacity='50'),dict(supported=True,params=PARAMS))
 def test_native_offset(self):
  with self.assertRaises(ValueError):native_style(dict(KEYS,shadowOffsetX='8'),dict(supported=True,params=PARAMS))
 def test_native_removed_shadow(self):
  with self.assertRaises(ValueError):native_style(dict(KEYS,shadow='0'),dict(supported=True,params=PARAMS))
 def test_undeclared_shadow(self):
  with self.assertRaises(ValueError):native_style(KEYS,None)
if __name__=='__main__':unittest.main()
