(root) => [...root.querySelectorAll('path,line,polyline')]
 .filter(el=>!el.closest('defs,marker,symbol,pattern,clipPath,mask') &&
   (()=>{for(let p=el;p;p=p.parentElement){const c=getComputedStyle(p);
     if(c.display==='none'||+c.opacity===0)return false;
     if(p===root)break;}return true;})() &&
   getComputedStyle(el).visibility==='visible' &&
   (getComputedStyle(el).markerStart!=='none'||getComputedStyle(el).markerEnd!=='none'))
 .map((el,index)=>{
   const a={};for(const key of ['x1','y1','x2','y2'])a[key]=el[key]?.baseVal?.value??+(el.getAttribute(key)||0);
   const matrix=el.getScreenCTM(),css=getComputedStyle(el);
   let cssDDeclared=!!(el.style.getPropertyValue('d')||el.style.getPropertyValue('all'));
   const inspect=rules=>{for(const rule of rules||[]){
     if(rule.style&&(rule.style.getPropertyValue('d')||rule.style.getPropertyValue('all'))){
       try{if(!rule.selectorText||el.matches(rule.selectorText))cssDDeclared=true;}catch(e){cssDDeclared=true;}
     }
     if(rule.cssRules)inspect(rule.cssRules);
   }};
   try{for(const sheet of document.styleSheets)inspect(sheet.cssRules);}catch(e){cssDDeclared=true;}
   return {index,element:el,descriptor:{tag:el.localName,d:el.getAttribute('d'),
     pointsAttr:el.getAttribute('points'),attrs:a,
     matrix:[matrix.a,matrix.b,matrix.c,matrix.d,matrix.e,matrix.f],
     computedD:css.d||'none',cssDDeclared,markerStart:css.markerStart,markerEnd:css.markerEnd}};
 })
