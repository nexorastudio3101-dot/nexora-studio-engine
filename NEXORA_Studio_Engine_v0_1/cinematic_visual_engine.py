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
    semantic=event.get("semantic",{})
    action=semantic.get("action","show")
    subject=semantic.get("subject","concept")
    objects=semantic.get("objects",[])
    relation=semantic.get("relationship","")
    before=semantic.get("state_before")
    after=semantic.get("state_after")
    metaphor=semantic.get("visual_metaphor")
    seq=int(event.get("sequence",0))
    total=max(1,int(event.get("sequence_total",1)))

    im=gradient(w,h,seed_for(event))
    d=ImageDraw.Draw(im)
    cx,cy=w//2,h//2+20

    # No branding or debug text belongs inside a scene.
    # Draw concrete semantic objects instead of generic "technology" graphics.
    def card(x,y,ww=190,hh=110,active=False):
        fill=(19,28,31) if not active else (24,43,37)
        outline=LIME if active else (73,91,94)
        d.rounded_rectangle((x-ww//2,y-hh//2,x+ww//2,y+hh//2),18,fill=fill,outline=outline,width=3)
        d.rectangle((x-ww//2+16,y-hh//2+16,x+ww//2-16,y-hh//2+28),fill=(45,59,62))
        d.ellipse((x-ww//2+24,y-hh//2+45,x-ww//2+42,y-hh//2+63),fill=LIME if active else (75,93,96))
        d.line((x-ww//2+52,y-hh//2+54,x+ww//2-24,y-hh//2+54),fill=(92,108,110),width=4)
        d.line((x-ww//2+24,y-hh//2+78,x+ww//2-45,y-hh//2+78),fill=(62,77,80),width=4)

    def person(x,y,active=False):
        d.ellipse((x-28,y-110,x+28,y-54),fill=(34,42,44),outline=WHITE,width=2)
        d.rounded_rectangle((x-55,y-54,x+55,y+105),22,fill=(20,31,34),outline=LIME if active else (70,87,90),width=3)

    def arrow(x1,y1,x2,y2,active=True):
        col=LIME if active else (71,91,94)
        d.line((x1,y1,x2,y2),fill=col,width=7)
        ang=math.atan2(y2-y1,x2-x1)
        p1=(x2-20*math.cos(ang-0.5),y2-20*math.sin(ang-0.5))
        p2=(x2-20*math.cos(ang+0.5),y2-20*math.sin(ang+0.5))
        d.polygon([(x2,y2),p1,p2],fill=col)

    if subject=="person" or action in ("switch","automate"):
        person(170,cy,active=action=="automate")

    if "tools" in objects or "tool" in objects or "AI tools" in objects:
        positions=[(430,210),(650,cy),(430,510)]
        for j,(x,y) in enumerate(positions):
            card(x,y,190,105,active=(action=="connect" and j==min(seq,2)))
        if action=="switch":
            arrow(270,cy,330,210,True); arrow(270,cy,330,cy,True); arrow(270,cy,330,510,True)
        elif before=="tools isolated" or action=="communicate":
            # Explicitly show separation/no communication.
            for x,y in positions:
                d.ellipse((x-112,y-67,x+112,y+67),outline=(47,58,61),width=2)
        elif action in ("connect","automate","decide"):
            # A central agent is the actual relationship described by the narration.
            card(870,cy,220,130,active=True)
            for x,y in positions:
                arrow(x+105,y,755,cy,True)
            if action in ("automate","decide"):
                arrow(980,cy,1120,cy,True)

    elif subject=="AI agent" or "AI agent" in objects:
        card(cx,cy,230,140,active=True)

    elif metaphor=="before_after":
        d.rounded_rectangle((100,170,560,570),28,fill=(15,22,25),outline=(72,87,90),width=3)
        d.rounded_rectangle((720,170,1180,570),28,fill=(18,32,27),outline=LIME,width=3)
        arrow(570,cy,710,cy,True)
    elif metaphor=="cause_effect":
        card(250,cy,220,125,False); card(640,cy,220,125,True); card(1030,cy,220,125,True)
        arrow(365,cy,525,cy,True); arrow(755,cy,915,cy,True)
    else:
        # Fallback is intentionally literal and restrained, not decorative circles.
        d.rounded_rectangle((cx-250,cy-130,cx+250,cy+130),28,fill=(17,27,30),outline=(71,90,93),width=3)
        d.line((cx-170,cy,cx+170,cy),fill=LIME,width=7)
        d.polygon([(cx+170,cy-14),(cx+200,cy),(cx+170,cy+14)],fill=LIME)

    # subtle background, no logos, labels or arbitrary technical overlays
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path,"PNG")
