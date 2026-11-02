"""Translate a complete editable graph by integer pixels and retain its old page."""
from decimal import Decimal
import xml.etree.ElementTree as E

def shift(xml,dx,dy,width,height):
    assert all(isinstance(v,int) for v in (dx,dy,width,height)) and min(dx,dy)>=0
    root=E.fromstring(xml);models=list(root.iter('mxGraphModel'));assert len(models)==1,'One uncompressed page required'
    model=models[0];ow=int(model.get('pageWidth'));oh=int(model.get('pageHeight'))
    assert width>=ow+dx and height>=oh+dy,'Original page must remain wholly visible'
    assert width-ow<=max(32,ow*.05) and height-oh<=max(32,oh*.05),'Expansion requires separate layout review'
    assert max(width,height)<=8192 and width*height<=64000000
    cr=model.find('root');cells={c.get('id'):c for c in cr if c.tag=='mxCell'}
    assert len(cells)==len(list(cr)),'Duplicate or wrapped cells require separate handling'
    changed=[]
    def add(e,key,delta):
        if delta:e.set(key,str(Decimal(e.get(key,'0'))+delta))
    for id,c in cells.items():
        if c.get('vertex')!='1' and c.get('edge')!='1':continue
        parent=c.get('parent');assert parent in cells,'Dangling parent'
        # Descendants inherit their graphic parent translation; do not move them twice.
        if cells[parent].get('vertex')=='1' or cells[parent].get('edge')=='1':continue
        g=c.find('mxGeometry');assert g is not None
        if c.get('vertex')=='1':
            assert g.get('relative','0')!='1','Relative top-level vertex requires separate handling'
            add(g,'x',dx);add(g,'y',dy)
            for alt in g.findall('mxRectangle'):
                assert alt.get('as')=='alternateBounds';add(alt,'x',dx);add(alt,'y',dy)
        else:
            assert g.get('relative')=='1','Nonrelative edge label requires separate handling'
            for child in g:
                if child.tag=='mxPoint' and child.get('as') in ('sourcePoint','targetPoint'):
                    add(child,'x',dx);add(child,'y',dy)
                elif child.tag=='Array':
                    assert child.get('as')=='points'
                    for point in child:assert point.tag=='mxPoint';add(point,'x',dx);add(point,'y',dy)
                else:assert child.tag=='mxPoint' and child.get('as')=='offset','Unsupported edge geometry child'
        changed.append(id)
    assert changed,'No editable graph objects'
    model.set('pageWidth',str(width));model.set('pageHeight',str(height))
    return E.tostring(root,encoding='unicode'),{'translation':[dx,dy],'old_page':[ow,oh],'new_page':[width,height],'translated_top_level_cells':changed,'text_style_topology_and_child_geometry_unchanged':True}
