import base64,io,struct,tempfile,unittest,zlib,sqlite3,json,contextlib
from pathlib import Path
from unittest.mock import patch
import arxiv_embedded_XML_parallel_prefilter_v1 as m
XML=b'<mxGraphModel><root><mxCell id="0"/></root></mxGraphModel>'
def chunk(kind,payload):return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)
def png(text_kind=b'tEXt',payload=None,after=False):
 payload=b'mxfile\0'+XML if payload is None else payload
 text=chunk(text_kind,payload);image=chunk(b'IDAT',b'p'*1000000)
 return b'\x89PNG\r\n\x1a\n'+(image+text if after else text+image)+chunk(b'IEND',b'')
class CountRead:
 def __init__(self,stream):self.stream=stream;self.bytes=0
 def read(self,n=-1):b=self.stream.read(n);self.bytes+=len(b);return b
 def __getattr__(self,key):return getattr(self.stream,key)
class MetadataPrefilterTest(unittest.TestCase):
 def decode(self,data):
  with tempfile.TemporaryFile() as f:
   f.write(data);f.seek(0);s=CountRead(f);result=m.png_xml(s);return result,s.bytes
 def test_PNG_text_without_pixel_payload_read(self):
  (blob,proof),reads=self.decode(png());self.assertEqual(blob,XML);self.assertTrue(proof['PNG_pixel_bytes_not_read']);self.assertLess(reads,300)
 def test_zlib_and_raw_deflate_text(self):
  for raw in (False,True):
   c=zlib.compressobj(wbits=-15 if raw else zlib.MAX_WBITS);data=c.compress(XML)+c.flush();(blob,_),_=self.decode(png(b'zTXt',b'mxfile\0\0'+data));self.assertEqual(blob,XML)
 def test_double_URI_and_malformed_URI(self):
  (blob,_),_=self.decode(png(payload=b'mxfile\0%253CmxGraphModel%252F%253E'));self.assertEqual(blob,b'<mxGraphModel/>')
  with self.assertRaises(ValueError):self.decode(png(payload=b'mxfile\0%GG'))
 def test_after_IDAT_and_CRC_fail_closed(self):
  with self.assertRaisesRegex(ValueError,'before_IDAT'):self.decode(png(after=True))
  data=bytearray(png());data[40]^=1
  with self.assertRaises(ValueError):self.decode(data)
 def test_inflate_resource_bound(self):
  with patch.object(m,'LIMIT',64):
   with self.assertRaises(ValueError):m.bounded_inflate(zlib.compress(b'a'*1000))
 def test_SVG_content_and_unsafe_DTD(self):
  for content in (b'&lt;mxGraphModel/&gt;',b'%3CmxGraphModel%2F%3E',base64.b64encode(b'<mxGraphModel/>')):
   self.assertEqual(m.svg_xml(b'<svg content="'+content+b'"/>')[0],b'<mxGraphModel/>')
  with self.assertRaises(ValueError):m.svg_xml(b'<!DOCTYPE svg [<!ENTITY x "boom">]><svg/>')
 def test_initial_queued_publication_has_no_false_candidates(self):
  with tempfile.TemporaryDirectory() as folder:
   c=sqlite3.connect(':memory:');c.execute('create table files(file text,status text,record text)');c.execute('insert into files values(?,?,?)',('queued.svg','queued',json.dumps(dict(file='queued.svg'))))
   with patch.object(m,'D',Path(folder)),contextlib.redirect_stdout(io.StringIO()):m.publish(c)
   status=json.loads((Path(folder)/'status.json').read_text());self.assertEqual(status['processed'],0);self.assertEqual(status['provisional_unique_graphs'],0);self.assertEqual(status['final_accepted_pairs'],0)
 def test_real_worker_preserves_provisional_XML_and_never_claims_final_QA(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);base=root/'clean/arxiv_research_figures_v1';source=base/'recent_ai_source_expansion_v2/papers/2301.1v1/source';source.mkdir(parents=True);dest=base/'prefilter';dest.mkdir();p=source/'framework.svg'
   vertices=''.join(f'<mxCell id="v{i}" vertex="1" value="Research module description {i}" parent="1"><mxGeometry x="{i*100}" y="0" width="80" height="40" as="geometry"/></mxCell>' for i in range(20))
   edges=''.join(f'<mxCell id="e{i}" edge="1" source="v{i}" target="v{(i+1)%20}" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>' for i in range(20))
   blob=('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'+vertices+edges+'</root></mxGraphModel>').encode();p.write_bytes(blob)
   with patch.object(m,'R',root),patch.object(m,'P',base),patch.object(m,'D',dest),patch.object(m,'KNOWN_RAW',set()):out=m.worker(dict(file=str(p.relative_to(root))))
   self.assertEqual(out['status'],'provisional_valuable_single_page_XML');self.assertFalse(out['final_QA']);self.assertEqual((root/out['embedded_XML_file']).read_bytes(),blob)
 def test_multi_page_held_before_decompression(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);base=root/'clean/arxiv_research_figures_v1';source=base/'recent_ai_source_expansion_v2/papers/2301.1v1/source';source.mkdir(parents=True);p=source/'test.svg';p.write_bytes(b'<mxfile><diagram>invalid</diagram><diagram>invalid</diagram></mxfile>')
   with patch.object(m,'R',root),patch.object(m,'P',base):out=m.worker(dict(file=str(p.relative_to(root))))
   self.assertEqual(out['status'],'multi_page_held_before_inflate');self.assertFalse(out['final_QA'])
if __name__=='__main__':unittest.main()
