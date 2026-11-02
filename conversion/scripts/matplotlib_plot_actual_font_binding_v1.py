"""Bind ordinary SVG Text to its captured physical Matplotlib face, never a CSS guess."""
def bind(page,scene,faces):
    artists={a['gid']:{'text':a['text'],'sha256':a['font_sha256']} for a in scene['artists'] if a.get('role')=='text' and a.get('font_sha256') and a.get('visible')}
    observed={f['sha256'] for f in scene['fonts'] if f.get('actual_SVG_renderer_font_observation')}
    inventory={f['sha256']:{'alias':f['alias'],'postscript':f['postscript'],'weight':f['weight'],'italic':f['italic']} for f in faces if f['sha256'] in observed}
    result=page.evaluate(r"""({artists,inventory})=>{let rows=[];for(const el of document.querySelectorAll('svg text')){let p=el;while(p&&!((p.id||'').startsWith('matplotlib_artist_')))p=p.parentElement;const a=artists[p?.id];if(!a)continue;
      // Plain text has one exact Artist string. Mathtext/tspan has per-run faces.
      const siblings=[...p.querySelectorAll('text')];const plain=siblings.every(e=>e.children.length===0)&&siblings.map(e=>e.textContent).join('\n')===a.text;if(el.children.length||!(el.textContent===a.text||plain))continue;const f=inventory[a.sha256];if(!f)throw Error('captured_Text_face_missing_actual_SVG_renderer_observation');
      rows.push({artist_gid:p.id,source_text:a.text,physical_font_sha256:a.sha256,postscript:f.postscript,original_SVG_style:el.getAttribute('style'),family_before:getComputedStyle(el).fontFamily,ordinary_Text_exact_GID_and_Unicode:true});el.style.fontFamily='"'+f.alias+'"';el.style.fontWeight=String(f.weight);el.style.fontStyle=f.italic?'italic':'normal';el.dataset.mplActualFace=a.sha256;}
      return rows;}""",{'artists':artists,'inventory':inventory})
    page.evaluate('document.fonts.ready')
    return {'contract':'captured_visible_Matplotlib_Text_gid_exact_full_Unicode_and_renderer_observed_face_v1','ordinary_texts_bound':len(result),'rows':result,'source_SVG_bytes_modified':False,'browser_view_only_font_binding':True,'reference_pixels_used':False,'source_code_reexecuted':False}
