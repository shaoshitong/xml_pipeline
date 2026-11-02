"""Versioned HTML source extraction: preserve wrapped words as editable line fragments."""
from pathlib import Path


def source_js(path):
    source = Path(path).read_text()
    old = 'const objects=[],unsupported=[];let serial=0;'
    assert old in source
    source = source.replace(old, '''const objects=[],unsupported=[];let serial=0;const qaElements=[...document.querySelectorAll("*")],qaMissing=[],qaWrappedWords=[];let qaEvent=0;''')
    source = source.replace('objects.push({', 'objects.push({qaOwner:qaElements.indexOf(el),qaOwnerTag:el.tagName,qaPaintEvent:++qaEvent,')
    source = source.replace('const txt=n.textContent;let groups=[];', 'const txt=n.textContent,qaTextEvent=++qaEvent;let groups=[];')
    old = "if(rects.length!==1){unsupported.push({reason:'word_spans_multiple_lines',text:match[0].slice(0,40)});continue;}"
    assert old in source
    source = source.replace(old, '''if(rects.length!==1){
      const split=qaSplitWord(n,match,el,cs,qaTextEvent);
      if(split.ok){qaMissing.push(...split.fragments);qaWrappedWords.push(split.proof);}
      else unsupported.push({reason:'word_grapheme_range_requires_review',text:match[0].slice(0,40),error:split.error});
      continue;
    }''')
    source = source.replace("groups.push({...box(b),text:match[0]});", "groups.push({...box(b),text:match[0],qaTextStart:match.index});")
    source = source.replace("type:'text',...g,color:", "type:'text',...g,qaPaintEvent:qaTextEvent,qaTextStart:g.qaTextStart,color:")
    marker = ' function walk(el){'
    assert marker in source
    function = r'''
 function qaSplitWord(n,match,el,cs,event){
  try{
   const graphemes=[...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(match[0])],fragments=[];let hidden='',rendered=0;
   for(const item of graphemes){
    const range=document.createRange(),start=match.index+item.index;
    range.setStart(n,start);range.setEnd(n,start+item.segment.length);
    const rects=[...range.getClientRects()].filter(r=>r.width&&r.height);
    if(!rects.length){if(fragments.length)fragments.at(-1).text+=item.segment;else hidden+=item.segment;continue;}
    if(rects.length!==1)throw Error('one grapheme occupies '+rects.length+' boxes');
    const r=rects[0],last=fragments.at(-1);rendered++;
    if(last&&Math.abs(last.y-r.y)<1&&Math.abs(last.h-r.height)<1){
     last.text+=hidden+item.segment;hidden='';const right=Math.max(last.x+last.w,r.right);last.x=Math.min(last.x,r.x);last.w=right-last.x;last.h=Math.max(last.h,r.height);
    }else{fragments.push({...box(r),text:hidden+item.segment,qaTextStart:start});hidden='';}
   }
   if(hidden&&fragments.length)fragments.at(-1).text+=hidden;
   if(fragments.map(f=>f.text).join('')!==match[0]&&rendered)throw Error('logical word characters did not roundtrip');
   let opacity=1;for(let a=el;a;a=a.parentElement)opacity*=+getComputedStyle(a).opacity;
   const visibleFragments=fragments.filter(g=>visible(g,el)).map((g,index)=>({
    ...g,sourceClip:clipInfo(g,el),type:'text',qaOwner:qaElements.indexOf(el),qaOwnerTag:el.tagName,
    qaPaintEvent:event,qaWrappedFragment:true,qaWordStart:match.index,qaWordText:match[0],qaFragmentIndex:index,
    color:rgba(cs.color),fontSize:parseFloat(cs.fontSize),fontFamilyRaw:cs.fontFamily,fontFamily:cs.fontFamily.split(',')[0].replace(/["']/g,''),
    bold:parseInt(cs.fontWeight)>=600||cs.fontWeight==='bold',italic:cs.fontStyle==='italic',underline:cs.textDecorationLine.includes('underline'),opacity
   }));
   return {ok:true,fragments:visibleFragments,proof:{owner:qaElements.indexOf(el),event,start:match.index,source_word:match[0],fragments:visibleFragments.map(g=>({text:g.text,x:g.x,y:g.y,w:g.w,h:g.h})),source_graphemes:graphemes.length,rendered_graphemes:rendered,all_logical_characters_preserved:fragments.map(f=>f.text).join('')===match[0],no_visible_source_glyphs:rendered===0}};
  }catch(e){return {ok:false,error:String(e)};}
 }
'''
    source = source.replace(marker, function+marker)
    source = source.replace('walk(document.body);return {objects,unsupported,width:', 'walk(document.body);for(const extra of qaMissing){extra.id=++serial;objects.push(extra);}return {qaWrappedWords,qaElementCount:qaElements.length,objects,unsupported,width:')
    return source
