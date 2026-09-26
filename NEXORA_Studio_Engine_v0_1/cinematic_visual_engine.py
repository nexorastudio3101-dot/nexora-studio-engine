from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LIME=(190,242,58)
WHITE=(242,246,245)
MUTED=(145,158,160)
BG=(7,11,14)


def font(size,bold=False):
    return ImageFont.truetype(BOLD if bold else FONT,size)


def seed_for(event):
    return int(hashlib.sha256((event.get("narration","")+event.get("type","")).encode()).hexdigest()[:8],16)


def gradient(w,h,seed):
    im=Image.new("RGB",(w,h))
    px=im.load()
    a=seed%360
    for y in range(h):
        for x in range(w):
            r=x/w; g=y/h
            glow=max(0,1-math.hypot(r-.72,g-.18)*1.5)
            px[x,y]=(int(7+9*glow),int(11+18*glow),int(14+24*glow))
    return im


def glow_dot(im,x,y,r,color,alpha=120):
    layer=Image.new("RGBA",im.size,(0,0,0,0))
    d=ImageDraw.Draw(layer)
    d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,alpha))
    layer=layer.filter(ImageFilter.GaussianBlur(max(8,r//2)))
    im.paste(layer,(0,0),layer)


def label(draw,text,x,y,size=20,color=MUTED):
    draw.text((x,y),text.upper(),font=font(size,True),fill=color)


def render_cinematic_frame(event,path,w=1920,h=1080):
    kind=event.get("type","context")
    seed=seed_for(event)
    im=gradient(w,h,seed)
    d=ImageDraw.Draw(im)
    # Editorial grid and subtle lime glow.
    for x in range(0,w,160):
        d.line((x,0,x,h),fill=(18,28,31),width=1)
    for y in range(0,h,135):
        d.line((0,y,w,y),fill=(18,28,31),width=1)
    glow_dot(im,int(w*.78),int(h*.2),260,LIME,55)
    glow_dot(im,int(w*.18),int(h*.82),180,(55,120,180),35)
    d=ImageDraw.Draw(im)

    title=event.get("label",kind).upper()
    label(d,"NEXORA / ACADEMY",90,62,18,LIME)
    d.line((90,104,1830,104),fill=(42,57,60),width=2)

    cx,cy=w//2,h//2+45
    if kind=="hook":
        for rr in (280,205,130):
            d.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline=(70,100,105),width=2)
        d.ellipse((cx-82,cy-82,cx+82,cy+82),fill=(24,35,37),outline=LIME,width=4)
        d.line((cx-82,cy,cx+82,cy),fill=LIME,width=4)
        d.line((cx,cy-82,cx,cy+82),fill=LIME,width=4)
        for i in range(12):
            ang=i*math.pi/6
            x=cx+330*math.cos(ang); y=cy+230*math.sin(ang)
            glow_dot(im,int(x),int(y),12,LIME,90)
    elif kind=="mechanism":
        nodes=[(420,cy),(760,cy-120),(1100,cy+120),(1500,cy)]
        for i,(x,y) in enumerate(nodes):
            if i:
                px,py=nodes[i-1]; d.line((px+70,py,x-70,y),fill=(85,112,113),width=4)
            d.ellipse((x-70,y-70,x+70,y+70),fill=(18,28,31),outline=LIME,width=4)
            d.ellipse((x-18,y-18,x+18,y+18),fill=LIME)
    elif kind=="contrast":
        d.rounded_rectangle((180,250,900,830),30,fill=(17,24,28),outline=(65,80,84),width=3)
        d.rounded_rectangle((1020,250,1740,830),30,fill=(20,31,27),outline=LIME,width=3)
        d.line((960,300,960,780),fill=(70,85,87),width=3)
        for y in (390,520,650):
            d.line((300,y,780,y),fill=(65,80,84),width=10)
            d.line((1140,y,1620,y),fill=LIME,width=10)
        d.text((300,875),"BEFORE",font=font(22,True),fill=MUTED)
        d.text((1140,875),"AFTER",font=font(22,True),fill=LIME)
    elif kind=="example":
        d.ellipse((cx-220,cy-220,cx+220,cy+220),fill=(17,27,31),outline=(70,105,110),width=3)
        d.rectangle((cx-125,cy-55,cx+125,cy+105),fill=(26,39,42),outline=LIME,width=3)
        d.ellipse((cx-35,cy-145,cx+35,cy-75),fill=(28,40,43),outline=WHITE,width=2)
        for i in range(5):
            d.line((cx+150,cy-160+i*80,cx+360,cy-160+i*80),fill=(80,104,107),width=5)
    elif kind=="takeaway":
        d.polygon([(cx,230),(cx+330,cy+360),(cx-330,cy+360)],fill=(18,29,31),outline=LIME)
        d.line((cx,260,cx,cy+260),fill=LIME,width=5)
        d.ellipse((cx-22,cy+230,cx+22,cy+274),fill=LIME)
        for r in (420,500):
            d.arc((cx-r,cy-r,cx+r,cy+r),205,335,fill=(60,82,85),width=3)
    else:
        # Context: connected constellation / knowledge map.
        pts=[(430,330),(720,470),(1010,300),(1260,520),(1510,350),(880,700),(1370,760)]
        for i,(x,y) in enumerate(pts):
            for j in range(i):
                x2,y2=pts[j]
                if math.hypot(x-x2,y-y2)<500:
                    d.line((x,y,x2,y2),fill=(44,66,70),width=3)
            d.ellipse((x-28,y-28,x+28,y+28),fill=(17,29,32),outline=LIME,width=3)
            glow_dot(im,x,y,35,LIME,50)
        d=ImageDraw.Draw(im)

    # A small semantic caption is deliberately derived from the scene type,
    # not the full narration, keeping the frame readable and premium.
    d.text((90,h-110),title,font=font(24,True),fill=WHITE)
    d.text((90,h-72),"NEXORA CINEMATIC VISUAL SYSTEM",font=font(15),fill=MUTED)
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); im.save(path,"PNG")
