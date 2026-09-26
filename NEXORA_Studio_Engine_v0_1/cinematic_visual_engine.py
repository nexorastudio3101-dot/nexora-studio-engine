from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

LIME=(190,242,58)
WHITE=(242,246,245)
MUTED=(130,145,148)
BG=(7,11,14)

def font(size,bold=False):
    name="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(name,size)

def seed_for(event):
    base="|".join([
        str(event.get("world","")),
        "|".join(event.get("persistent_concepts",[])),
        str(event.get("sequence",0)),
    ])
    return int(hashlib.sha256(base.encode()).hexdigest()[:8],16)

def gradient(w,h,seed):
    yy,xx=np.mgrid[0:h,0:w]
    rx=xx.astype(np.float32)/w
    ry=yy.astype(np.float32)/h
    glow=np.clip(1.0-np.sqrt((rx-.72)**2+(ry-.18)**2)*1.5,0,1)
    arr=np.zeros((h,w,3),dtype=np.uint8)
    arr[:,:,0]=(7+9*glow).astype(np.uint8)
    arr[:,:,1]=(11+18*glow).astype(np.uint8)
    arr[:,:,2]=(14+24*glow).astype(np.uint8)
    return Image.fromarray(arr,"RGB")

def glow_dot(im,x,y,r,color,alpha=120):
    layer=Image.new("RGBA",im.size,(0,0,0,0))
    d=ImageDraw.Draw(layer)
    d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,alpha))
    layer=layer.filter(ImageFilter.GaussianBlur(max(6,r//2)))
    im.paste(layer,(0,0),layer)

def node(d,im,x,y,r=42,active=False):
    outline=LIME if active else (67,91,95)
    fill=(20,31,34) if not active else (25,40,38)
    d.ellipse((x-r,y-r,x+r,y+r),fill=fill,outline=outline,width=3)
    if active:
        glow_dot(im,x,y,int(r*.9),LIME,45)
        d=ImageDraw.Draw(im)
        d.ellipse((x-8,y-8,x+8,y+8),fill=LIME)

def render_cinematic_frame(event,path,w=1280,h=720):
    kind=event.get("type","concept")
    world=event.get("world","abstract_system")
    seq=int(event.get("sequence",0))
    total=max(1,int(event.get("sequence_total",1)))
    seed=seed_for(event)
    im=gradient(w,h,seed)
    d=ImageDraw.Draw(im)

    # Clean cinematic frame: no debug labels, no scene-type captions.
    for x in range(0,w,128):
        d.line((x,0,x,h),fill=(17,27,30),width=1)
    for y in range(0,h,90):
        d.line((0,y,w,y),fill=(17,27,30),width=1)

    glow_dot(im,int(w*.78),int(h*.2),180,LIME,42)
    glow_dot(im,int(w*.16),int(h*.82),130,(55,120,180),30)
    d=ImageDraw.Draw(im)

    cx,cy=w//2,h//2+15
    # The same visual world evolves from scene to scene.
    if world in ("technology","data","abstract_system"):
        if kind == "hook":
            # Fragmented elements: the visual problem is established.
            pts=[(250,250),(460,430),(680,220),(900,430),(1100,250)]
            for x,y in pts:
                node(d,im,x,y,38,False)
            d.line((288,250,422,410),fill=(53,72,76),width=3)
            d.line((498,430,642,235),fill=(53,72,76),width=3)
            d.line((718,235,862,410),fill=(53,72,76),width=3)
            d.line((938,410,1062,265),fill=(53,72,76),width=3)
        elif kind in ("concept","process"):
            # The fragments begin to organize into a system.
            pts=[(300,300),(510,220),(510,500),(760,360),(1010,220),(1010,500)]
            links=[(0,1),(0,3),(1,3),(2,3),(3,4),(3,5)]
            for a,b in links:
                x1,y1=pts[a]; x2,y2=pts[b]
                d.line((x1,y1,x2,y2),fill=(62,87,90),width=4)
            for j,(x,y) in enumerate(pts):
                node(d,im,x,y,38,j==3 or j==seq%len(pts))
        elif kind == "cause_effect":
            pts=[(250,360),(500,260),(750,360),(1000,260)]
            for j in range(len(pts)-1):
                x1,y1=pts[j]; x2,y2=pts[j+1]
                d.line((x1+45,y1,x2-45,y2),fill=LIME if j==min(seq,2) else (65,88,91),width=6)
                d.polygon([(x2-55,y2-10),(x2-38,y2),(x2-55,y2+10)],fill=LIME if j==min(seq,2) else (65,88,91))
            for j,(x,y) in enumerate(pts): node(d,im,x,y,44,j==min(seq,3))
        elif kind == "contrast":
            d.rounded_rectangle((120,180,570,570),28,fill=(16,24,27),outline=(68,82,85),width=3)
            d.rounded_rectangle((710,180,1160,570),28,fill=(19,32,27),outline=LIME,width=3)
            for y in (270,360,450):
                d.line((210,y,480,y),fill=(66,82,85),width=12)
                d.line((800,y,1070,y),fill=LIME,width=12)
        elif kind == "example":
            # A simple human-scale scene linked to the system.
            d.ellipse((cx-44,cy-180,cx+44,cy-92),fill=(25,36,39),outline=WHITE,width=2)
            d.rounded_rectangle((cx-82,cy-90,cx+82,cy+145),25,fill=(19,31,34),outline=LIME,width=3)
            for x,y in ((260,300),(1020,300),(260,470),(1020,470)):
                d.line((x,y,cx-100 if x<cx else cx+100, y),fill=(65,88,91),width=4)
                node(d,im,x,y,30,True)
        else:
            # Resolution: the system is unified.
            d.ellipse((cx-120,cy-120,cx+120,cy+120),fill=(21,38,34),outline=LIME,width=5)
            for i in range(8):
                a=i*math.pi/4
                x=cx+280*math.cos(a); y=cy+210*math.sin(a)
                d.line((x,y,cx+110*math.cos(a),cy+110*math.sin(a)),fill=LIME,width=5)
                node(d,im,int(x),int(y),28,True)
            for r in (170,220,270):
                d.arc((cx-r,cy-r,cx+r,cy+r),210,330,fill=(58,80,83),width=3)
    elif world=="human_system":
        # Persistent human + surrounding system.
        head=(cx,cy-150); body=(cx,cy+50)
        d.ellipse((head[0]-48,head[1]-48,head[0]+48,head[1]+48),fill=(25,36,39),outline=WHITE,width=2)
        d.rounded_rectangle((body[0]-95,body[1]-100,body[0]+95,body[1]+130),28,fill=(19,31,34),outline=LIME,width=3)
        for a in range(6):
            ang=a*math.pi/3
            x=cx+330*math.cos(ang); y=cy+220*math.sin(ang)
            node(d,im,int(x),int(y),34,a<=seq%6)
            d.line((x,y,cx,body[1]),fill=(58,82,85),width=3)
    else:
        # Abstract system: a coherent transformation across scenes.
        progress=seq/max(1,total-1)
        r=90+int(180*progress)
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=LIME,width=5)
        for i in range(12):
            a=i*math.pi/6+progress
            x=cx+(r+80)*math.cos(a); y=cy+(r+55)*math.sin(a)
            node(d,im,int(x),int(y),24,i<=int(progress*11))
            d.line((x,y,cx+r*math.cos(a),cy+r*math.sin(a)),fill=(58,82,85),width=3)

    # Minimal brand mark only; no debug metadata or scene labels.
    d.text((42,34),"NEXORA",font=font(18,True),fill=LIME)

    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path,"PNG")
