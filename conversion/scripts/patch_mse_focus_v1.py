"""Locate image differences without gold XML. Bounds use target PNG pixels."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter


def on_white(path):
    with Image.open(path) as source:
        im = source.convert('RGBA')
    white = Image.new('RGBA', im.size, 'white')
    white.alpha_composite(im)
    return white.convert('RGB')


def registration(target, candidate, radius=8):
    # Match the dominant extent with a uniform resize. Fit a small translation
    # using blurred ink, so the alignment is less sensitive to a one-pixel stroke.
    axis = int(target.height > target.width)
    scale = target.size[axis] / candidate.size[axis]
    src = candidate.resize(tuple(max(1, round(v*scale)) for v in candidate.size), Image.Resampling.LANCZOS)
    w,h = target.size
    target_ink = 1 - np.array(target.convert('L'),dtype=np.float32)/255
    src_ink = 1 - np.array(src.convert('L'),dtype=np.float32)/255
    a = gaussian_filter(target_ink,2)[::2,::2]
    b = gaussian_filter(src_ink,2)
    fit = []
    for dy in range(-radius,radius+1):
        for dx in range(-radius,radius+1):
            padded = np.zeros((h,w),dtype=np.float32)
            x0,y0,x1,y1 = max(0,dx),max(0,dy),min(w,src.width+dx),min(h,src.height+dy)
            if x1>x0 and y1>y0:
                padded[y0:y1,x0:x1] = b[y0-dy:y1-dy,x0-dx:x1-dx]
            score = float(np.mean((a-padded[::2,::2])**2))
            fit.append((score,abs(dx)+abs(dy),dx,dy))
    best = min(fit)
    return dict(dx=best[2],dy=best[3],scale=scale,axis=axis,radius=radius,
                fit_ink_mse=best[0],fit_ink_mse_at_zero_shift=next(z[0] for z in fit if z[2:]==(0,0)),
                touches_search_boundary=max(abs(best[2]),abs(best[3]))==radius)


def features(target, candidate, transform):
    frame = Image.new('RGB',target.size,'white')
    src = candidate.resize(tuple(max(1,round(v*transform['scale'])) for v in candidate.size),Image.Resampling.LANCZOS)
    frame.paste(src,(transform['dx'],transform['dy']))
    a,b = (np.asarray(im,dtype=np.float32)/255 for im in (target,frame))
    fa,fb = np.any(a<.88,axis=2),np.any(b<.88,axis=2)
    err = np.mean((a-b)**2,axis=2)
    # Use lightly blurred error only for ranking; raw MSE is still reported.
    smooth_a,smooth_b = (gaussian_filter(arr,(.8,.8,0)) for arr in (a,b))
    smooth = np.mean((smooth_a-smooth_b)**2,axis=2)
    return frame,err,smooth,fa,fb


def score(bbox,err,smooth,fa,fb):
    x0,y0,x1,y1 = bbox
    sl = (slice(y0,y1),slice(x0,x1))
    a,b = fa[sl],fb[sl]
    union = a|b
    coverage = float(union.mean())
    smooth_fg = float(smooth[sl][union].mean()) if union.any() else 0.
    return dict(bbox=list(bbox),mse=float(err[sl].mean()),
                foreground_mse=float(err[sl][union].mean()) if union.any() else 0.,
                ranking_score=smooth_fg*coverage**.5,foreground_coverage=coverage,
                target_only_ink_px=int((a&~b).sum()),candidate_only_ink_px=int((b&~a).sum()),
                foreground_iou=float((a&b).sum()/max(1,union.sum())))


def overlap(a,b):
    x0,y0,x1,y1 = a
    u0,v0,u1,v1 = b
    area = max(0,min(x1,u1)-max(x0,u0))*max(0,min(y1,v1)-max(y0,v0))
    return area/max(1,min((x1-x0)*(y1-y0),(u1-u0)*(v1-v0)))


def positions(n,window,stride):
    return sorted(set(range(0,max(1,n-window+1),stride))|{max(0,n-window)})


def locate(w,h,metrics):
    proposals = []
    for window,stride in [(48,24),(80,40)]:
        for y in positions(h,window,stride):
            for x in positions(w,window,stride):
                item = score((x,y,min(w,x+window),min(h,y+window)),*metrics)
                if item['foreground_coverage']>=.08 and item['ranking_score']>1e-6:
                    proposals.append(item)
    selected = []
    for item in sorted(proposals,key=lambda p:-p['ranking_score']):
        if all(overlap(item['bbox'],old['bbox'])<.25 for old in selected):
            selected.append(dict(id=f'P{len(selected)+1}',**item))
            if len(selected)>=5:
                break
    return selected


def diff_image(a, b, intensity):
    # Magenta: target ink missing; blue: candidate extra ink; orange: color/other error.
    heat = np.full((*a.shape,3),255,dtype=np.uint8)
    for mask,rgb in [(a&~b,(207,20,111)),(b&~a,(26,90,211)),(a&b&(intensity>.03),(234,131,22))]:
        heat[mask] = rgb
    return Image.fromarray(heat)


def previews(folder,target,frame,heat,regions):
    labels = ('Target','Candidate aligned','Difference: pink missing / blue extra')
    w,h = target.size
    grid = Image.new('RGB',(w,3*(h+20)),'white')
    for j,image in enumerate((target,frame,heat)):
        y0=j*(h+20)
        grid.paste(image,(0,y0+20))
        draw=ImageDraw.Draw(grid)
        draw.text((3,y0+3),labels[j],fill='black')
        for item in regions:
            x,y,x1,y1=item['bbox']; y+=y0+20; y1+=y0+20
            draw.rectangle((x,y,x1-1,y1-1),outline='#d13514',width=2)
            draw.rectangle((x,y,x+22,y+13),fill='white')
            draw.text((x+2,y+1),item['id'],fill='#851d0a')
    grid.save(folder/'overview.png')
    for item in regions:
        x,y,x1,y1 = item['bbox']
        box = (max(0,x-20),max(0,y-20),min(w,x1+20),min(h,y1+20))
        cw,ch = 3*(box[2]-box[0]),3*(box[3]-box[1])
        sheet = Image.new('RGB',(3*cw,ch+20),'white')
        draw = ImageDraw.Draw(sheet)
        for i,(im,label) in enumerate(zip((target,frame,heat),labels)):
            sheet.paste(im.crop(box).resize((cw,ch),Image.Resampling.NEAREST),(i*cw,20))
            draw.text((i*cw+2,3),label,fill='black')
            draw.rectangle((i*cw+3*(x-box[0]),20+3*(y-box[1]),i*cw+3*(x1-box[0])-1,20+3*(y1-box[1])-1),outline='#d13514',width=2)
        sheet.save(folder/(item['id']+'.png'))


def main():
    start = time.monotonic()
    p = argparse.ArgumentParser()
    p.add_argument('target',type=Path)
    p.add_argument('candidate',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--freeze',type=Path,help='reuse baseline transform and identical patch boxes for after scoring')
    p.add_argument('--baseline-image',type=Path,help='with --freeze, measure changes outside P1 and an expanded ROI')
    args = p.parse_args()
    target,candidate = on_white(args.target),on_white(args.candidate)
    before = json.loads(args.freeze.read_text()) if args.freeze else None
    transform = before['transform'] if before else registration(target,candidate)
    frame,*metrics = features(target,candidate,transform)
    regions = ([dict(id=old['id'],**score(old['bbox'],*metrics)) for old in before['patches']]
               if before else locate(*target.size,metrics))
    args.output.mkdir(parents=True,exist_ok=True)
    heat = diff_image(metrics[-2],metrics[-1],metrics[0])
    previews(args.output,target,frame,heat,regions)
    result = dict(target_size=target.size,candidate_size=candidate.size,transform=transform,
                  warning='Pixel differences are diagnostic, not semantic checks. Pink/blue also appear on shifted edges.',
                  coordinates='zero-based [x0,y0,x1,y1), target PNG pixels, not XML canvas coordinates',
                  transform_frozen=bool(before),global_metrics=score((0,0,*target.size),*metrics),patches=regions,
                  seconds=round(time.monotonic()-start,3))
    if args.baseline_image:
        if not before or not regions:
            raise ValueError('--baseline-image requires a frozen comparison with a P1 patch')
        baseline = on_white(args.baseline_image)
        old_frame,*old_metrics = features(target,baseline,transform)
        x,y,x1,y1 = regions[0]['bbox']
        x,y,x1,y1 = max(0,x-20),max(0,y-20),min(target.width,x1+20),min(target.height,y1+20)
        outside = np.ones((target.height,target.width),dtype=bool)
        outside[y:y1,x:x1] = False
        changed = np.any(np.asarray(old_frame)!=np.asarray(frame),axis=2)
        result['scope_check'] = dict(roi=[x,y,x1,y1],same_tight_render_dimensions=baseline.size==candidate.size,
            roi_before=score((x,y,x1,y1),*old_metrics),roi_after=score((x,y,x1,y1),*metrics),
            changed_pixels_inside_roi=int((changed&~outside).sum()),changed_pixels_outside_roi=int((changed&outside).sum()),
            outside_roi_mse_before=float(old_metrics[0][outside].mean()),outside_roi_mse_after=float(metrics[0][outside].mean()))
    (args.output/'patch_feedback.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
