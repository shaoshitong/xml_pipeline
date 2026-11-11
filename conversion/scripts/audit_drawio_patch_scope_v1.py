"""Compare cell changes and the native rectangular grid in the audited group."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def load(path):
    mx = ET.parse(path).getroot()
    model = mx if mx.tag=='mxGraphModel' else mx.find('diagram/mxGraphModel')
    if model is None:
        raise ValueError('requires a single uncompressed draw.io model')
    cells = {c.get('id'):c for c in model.find('root')}
    return cells,dict(model.attrib)


def shape(cells,group):
    coordinates = []
    for c in cells.values():
        if c.get('parent')==group and c.get('vertex')=='1':
            g = c.find('mxGeometry')
            coordinates.append((float(g.get('x',0)),float(g.get('y',0))))
    xs,ys = {x for x,y in coordinates},{y for x,y in coordinates}
    return dict(rows=len(ys),columns=len(xs),editable_cells=len(coordinates),
                complete_grid=len(xs)*len(ys)==len(set(coordinates))==len(coordinates))


def element(c):
    return (c.tag,tuple(sorted(c.attrib.items())),tuple(element(v) for v in c))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('before',type=Path)
    p.add_argument('after',type=Path)
    p.add_argument('group')
    args = p.parse_args()
    old, old_header = load(args.before)
    new, new_header = load(args.after)
    added,removed,modified = set(new)-set(old),set(old)-set(new),{k for k in old.keys()&new.keys() if element(old[k])!=element(new[k])}
    touched=added|removed|modified
    def in_group(cid):
        return cid==args.group or any(cid in cells and cells[cid].get('parent')==args.group for cells in (old,new))
    print(json.dumps(dict(before=shape(old,args.group),after=shape(new,args.group),
                          added=sorted(added),removed=sorted(removed),modified=sorted(modified),
                          outside_group=sorted(k for k in touched if not in_group(k)),
                          model_header_unchanged=old_header==new_header),indent=2))


if __name__=='__main__':
    main()
