from pathlib import Path
import shutil,subprocess,unittest

class PaintPrecisionTests(unittest.TestCase):
 def test_actual_binary32_rounding_and_real_paint_negatives(self):
  node=shutil.which('node')
  if not node:self.skipTest('node is unavailable; real browser controls required separately')
  helper=str(Path(__file__).with_name('tikz_editing_paint_precision_v1.js'))
  script=r'''
const assert=require('assert'),p=require(process.argv[1]);
const actualBefore={x:2062.860107421875,y:91.77999877929688,width:137.789794921875,height:39.3699951171875};
const actualAfter={x:2049.85986328125,y:110.77999877929688,width:137.7900390625,height:39.3699951171875};
assert(p.prove(actualBefore,actualAfter,{x:-13,y:19}).ok);
assert(!p.prove(actualBefore,{...actualAfter,x:actualAfter.x+.25*100/72},{x:-13,y:19}).ok);
assert(!p.prove(actualBefore,{...actualAfter,width:actualAfter.width+.002},{x:-13,y:19}).ok);
assert(!p.prove(actualBefore,actualBefore,{x:17,y:11}).ok);
const f=Math.fround,box=(x,y,w,h)=>({x:f(x),y:f(y),width:f(x+w)-f(x),height:f(y+h)-f(y)});
for(const x of [0,8,100,511.9,1024.1,2062.86,4095.9,8191.3])for(const offset of [{x:17,y:11},{x:-13,y:19}]){
 const b=box(x,91.78,137.79,39.37),a=box(x+offset.x,91.78+offset.y,137.79,39.37);
 assert(p.prove(b,a,offset).ok,JSON.stringify({b,a,offset}));
 assert(!p.prove(b,{...a,x:a.x+.002},offset).ok);
 assert(!p.prove(b,{...a,width:a.width+.25*100/72},offset).ok);
}
assert(!p.prove({x:1e8,y:0,width:1,height:1},{x:1e8+17,y:11,width:1,height:1},{x:17,y:11}).ok);
assert(!p.prove(actualBefore,{...actualAfter,x:NaN},{x:-13,y:19}).ok);
assert.strictEqual(p.binary32HalfUlp(2062),2**-13);
console.log('paint precision controls passed');
'''
  result=subprocess.run([node,'-e',script,helper],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
