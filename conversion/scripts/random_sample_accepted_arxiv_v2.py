"""Uniform accepted-only sample; unchanged code/PNG bytes and resource closure."""
from pathlib import Path
from urllib.parse import quote
import argparse,datetime,hashlib,html,json,random,shutil,struct,zipfile
from PIL import Image,ImageDraw,ImageFont,ImageOps
from arxiv_author_native_assets_v1 import dependencies
from arxiv_author_native_asset_package_v1 import package
R=Path('/backup/shaoshitong/img2code_20261029')
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--index',required=True);p.add_argument('--expected-sha',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--name',required=True);p.add_argument('--final',action='store_true');a=p.parse_args()
 assert Path(a.name).name==a.name and a.name not in {'.','..'}
 raw=(R/a.index).read_bytes();assert sha(raw)==a.expected_sha
 rows=[json.loads(l) for l in raw.splitlines()];assert len(rows)>=100
 if a.final:assert len(rows)>=500,'final_accepted_cohort_below500'
 assert len({r['goal500_pair_id'] for r in rows})==len(rows)
 for r in rows:
  assert 'arxiv_author_native_source_replay' in r['quality_views']
  if not r.get('scientific_value_individually_certified'):
   assert r.get('accepted_authoritative') and r.get('automatic_admission_policy') and r.get('automatic_admission_proof')
   p=R/r['automatic_admission_proof'];e=p.read_bytes();assert sha(e)==r['automatic_admission_proof_sha256'];q=json.loads(e)
   assert q['code_sha256']==r['code_sha256'] and q['image_sha256']==r['image_sha256']
   assert all(q.get(k) is True for k in ['actual_RGBA_edit_changed','actual_PNG_restore_exact','actual_SVG_restore_exact','resources_closed','physical_font_bytes_pinned','source_container_unchanged']) and q['layout']['ok']
   if r.get('source_origin_kind')=='embedded_native_complete_page':assert q['complete_page_identity']['all_original_cells_edges_groups_styles_geometry_labels_and_order_preserved']
 selected=random.Random(a.seed).sample(rows,100);out=R/'clean/review_samples'/a.name;out.mkdir(parents=True,exist_ok=False)
 (out/'population.jsonl').write_bytes(raw);records=[];cards=[];thumbs=[]
 with zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war') as war:
  for number,row in enumerate(selected,1):
   code=R/row['code_file'];image=R/row['image_file'];xml=code.read_bytes();blob=image.read_bytes()
   assert sha(xml)==row['code_sha256'] and sha(blob)==row['image_sha256']
   proof=(R/row['native_replay_proof']).read_bytes();assert sha(proof)==row['native_replay_proof_sha256'] and json.loads(proof)['ok']
   dep=dependencies(xml,code,R/row['original_PDF_file'] if row.get('original_PDF_file') else code,war)
   assert not dep['issues'],'accepted resource closure missing'
   folder=out/'pairs'/f'{number:03d}';folder.mkdir(parents=True)
   if dep['asset_map']:
    target,assets,meta=package(xml,dep,folder/'editable')
   else:
    target=folder/code.name;target.write_bytes(xml);assets={};meta=None
   assert target.read_bytes()==xml
   closed=dependencies(target.read_bytes(),target,target,war);assert not closed['issues']
   (folder/'image.png').write_bytes(blob);(folder/'source_replay_proof.json').write_bytes(proof)
   for proof_key in ['automatic_admission_proof','page_selection_proof','official_decoder_agreement','official_full_decoder_agreement','official_page_decoder_comparison','archive_membership_proof']:
    if row.get(proof_key):
     extra=(R/row[proof_key]).read_bytes();assert sha(extra)==row[proof_key+'_sha256'];(folder/(proof_key+'.json')).write_bytes(extra)
   with Image.open(image) as im:
    rgba=im.convert('RGBA');w,h=rgba.size
    assert row['image_pixels']==dict(width=w,height=h,rgba_sha256=sha(struct.pack('>QQ',w,h)+rgba.tobytes()))
    white=Image.new('RGBA',rgba.size,'white');white.alpha_composite(rgba);thumbs.append(ImageOps.contain(white.convert('RGB'),(390,270)))
   localcode=str(target.relative_to(out));localimage=str((folder/'image.png').relative_to(out));esc=html.escape;codehref=esc(quote(localcode,safe='/'))
   cards.append(f'<article><h2>#{number:03d} · {esc(row["paper"])}</h2><a href="{localimage}"><img loading="lazy" src="{localimage}" alt="#{number:03d}"></a><p><a href="{localimage}">PNG 成品</a> · <a download href="{codehref}">可编辑 drawio/XML</a> · <a href="pairs/{number:03d}/source_replay_proof.json">重放核验</a></p></article>')
   records.append(dict(number=number,local_code=localcode,local_image=localimage,resource_assets_copied=len(assets),portable_package=meta,source_record=row))
   if number%25==0:print(json.dumps(dict(copied_pairs=number)),flush=True)
 manifest=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),population=len(rows),sampled=100,seed=a.seed,sampling='uniform random without replacement; accepted-only frozen population; no visual replacements',index=a.index,index_sha256=a.expected_sha,milestone_preview_not_final_goal_acceptance=not a.final,final_500plus_preview=a.final,code_and_PNG_bytes_unchanged=True,source_replay_is_not_original_PDF_fidelity=True,font_dependencies_remain_runtime_declared_not_bundled=True,records=records)
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
 except OSError:font=ImageFont.load_default()
 for page in range(4):
  sheet=Image.new('RGB',(2000,1550),'#e9edf2');draw=ImageDraw.Draw(sheet)
  for cell,thumb in enumerate(thumbs[page*25:(page+1)*25]):
   x=(cell%5)*400;y=(cell//5)*310;sheet.paste(thumb,(x+(400-thumb.width)//2,y+8+(270-thumb.height)//2));n=page*25+cell+1;draw.text((x+8,y+285),f'#{n:03d} {selected[n-1]["paper"]}',font=font,fill='#182434')
  sheet.save(out/f'overview_{page+1}.jpg',quality=92)
 completion_text='新增500对阶段目标的成品抽样。' if a.final else '本预览为阶段成果，新增500对目标尚未完成。'
 intro=f'从已验收新增成品 {len(rows)} 对中均匀无放回抽取100对；种子 {a.seed}。未按效果替换样本。PNG和代码保持原字节，资源依赖已检查。源码重放与原始PDF保真分别记录；字体依赖详见清单。{completion_text}'
 (out/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新增成品随机100对</title><style>body{background:#eef1f5;color:#172333;font:16px system-ui;margin:24px}main{max-width:1600px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}article{background:white;padding:16px;border-radius:8px}h2{font-size:17px}img{width:100%;height:340px;object-fit:contain}p{line-height:1.7}a{color:#145ba0}</style><main><h1>新增成品随机100对</h1><p>'+html.escape(intro)+'</p><p><a href="manifest.json">抽样与核验清单</a></p><div class="grid">'+''.join(cards)+'</div></main></html>')
 files={str(q.relative_to(out)):dict(sha256=sha(q.read_bytes()),bytes=q.stat().st_size) for q in sorted(out.rglob('*')) if q.is_file()};(out/'files.json').write_text(json.dumps(files,indent=2)+'\n')
 archive=out.with_suffix('.zip')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for q in sorted(out.rglob('*')):
   if q.is_file():z.write(q,str(q.relative_to(out.parent)))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for name,meta in files.items():assert sha(z.read(out.name+'/'+name))==meta['sha256']
 receipt=dict(root=str(out),archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive.read_bytes()),population=len(rows),sampled=100,seed=a.seed,index_sha256=a.expected_sha,verified_payload_files=len(files),all_archive_hashes_verified=True)
 out.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
