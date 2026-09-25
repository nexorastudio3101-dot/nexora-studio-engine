from __future__ import annotations
from typing import Callable, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1920,1080
BG=(18,23,28); CARD=(34,42,49); WHITE=(239,242,244); MUTED=(150,160,166); LIME=(194,215,72); LINE=(67,79,87)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(n,b=False): return ImageFont.truetype(BOLD if b else FONT,n)
def base():
 im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im)
 for x in range(90,W,240): d.line((x,0,x,H),fill=(27,35,41),width=1)
 for y in range(120,H,190): d.line((0,y,W,y),fill=(27,35,41),width=1)
 g=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(g).ellipse((100,20,650,500),fill=(*LIME,10))
 return Image.alpha_composite(im.convert('RGBA'),g.filter(ImageFilter.GaussianBlur(110))).convert('RGB')
def header(im): d=ImageDraw.Draw(im); d.text((110,65),'NEXORA ACADEMY',font=f(20,True),fill=LIME); d.line((110,105,1810,105),fill=(48,58,64),width=2)
def rr(d,b,fill=CARD,outline=LINE,w=1,r=18): d.rounded_rectangle(b,radius=r,fill=fill,outline=outline,width=w)
def center_text(d,text,y,size=54,fill=WHITE,b=False): d.text((960,y),text,font=f(size,b),fill=fill,anchor='mm')
def question(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','WHAT EXACTLY IS AN'),405,44,MUTED,True); center_text(d,e.get('subtitle','AI AGENT?'),535,96,WHITE,True); d.rounded_rectangle((660,612,1260,620),4,fill=LIME); return im
def concept(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','CONCEPT'),360,70,WHITE,True); center_text(d,e.get('body',''),500,34,MUTED); return im
def definition(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','DEFINITION'),300,60,WHITE,True); rr(d,(380,390,1540,700),CARD,LIME,2,24); center_text(d,e.get('term',''),455,34,LIME,True); center_text(d,e.get('definition',''),560,38,WHITE); return im
def tools(e,t):
 im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','AI TOOLS'),255,70,WHITE,True); center_text(d,e.get('subtitle','Examples of what they can do'),370,28,MUTED)
 labels=e.get('items') or ['WRITE','SUMMARIZE','ANSWER QUESTIONS','GENERATE IMAGES','ANALYZE DATA']; pos=[(590,540),(960,540),(1330,540),(775,750),(1145,750)]
 for lab,(x,y) in zip(labels,pos):
  ww=280 if len(lab)<14 else 350; b=(x-ww/2,y-47,x+ww/2,y+47); active=e.get('active')
  if lab==active: rr(d,b,CARD,LIME,2); d.text((x,y),lab,font=f(26,True),fill=WHITE,anchor='mm')
  else: rr(d,b,(30,38,44),LINE,1); d.text((x,y),lab,font=f(25,True),fill=MUTED,anchor='mm')
 return im
def comparison(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','COMPARISON'),250,62,WHITE,True); rr(d,(260,400,900,730),CARD,LINE,2); rr(d,(1020,400,1660,730),CARD,LIME,2); d.text((580,470),e.get('left',''),font=f(42,True),fill=WHITE,anchor='mm'); d.text((1340,470),e.get('right',''),font=f(42,True),fill=WHITE,anchor='mm'); d.text((960,565),'VS',font=f(34,True),fill=LIME,anchor='mm'); return im
def process(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','PROCESS'),235,62,WHITE,True); steps=e.get('items') or ['GOAL','PLAN','ACT','CHECK','RESULT']; n=len(steps); gap=260; start=960-(n-1)*gap/2
 for i,s in enumerate(steps):
  x=start+i*gap; d.ellipse((x-48,470,x+48,566),outline=LIME,width=3); d.text((x,518),str(i+1),font=f(30,True),fill=WHITE,anchor='mm'); d.text((x,640),s,font=f(24,True),fill=WHITE,anchor='mm')
  if i<n-1: d.line((x+55,518,x+gap-55,518),fill=LINE,width=3)
 return im
def list_scene(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','KEY POINTS'),250,62,WHITE,True); 
 # list body intentionally simple for cloud stability
 for i,item in enumerate((e.get('items') or [])[:6]): y=380+i*85; d.ellipse((470,y-7,484,y+7),fill=LIME); d.text((520,y),item,font=f(30),fill=WHITE,anchor='lm')
 return im
def before_after(e,t): return comparison({**e,'title':e.get('title','BEFORE → AFTER'),'left':e.get('before','BEFORE'),'right':e.get('after','AFTER')},t)
def takeaway(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,'KEY TAKEAWAY',330,34,LIME,True); center_text(d,e.get('text',''),520,58,WHITE,True); return im
def conclusion(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','THAT’S THE IDEA.'),470,72,WHITE,True); center_text(d,e.get('subtitle',''),560,32,MUTED); return im
def shift(e,t): im=base(); header(im); d=ImageDraw.Draw(im); center_text(d,e.get('title','BUT AN AI AGENT'),330,44,MUTED,True); center_text(d,e.get('subtitle','TAKES THIS IDEA'),450,68,WHITE,True); center_text(d,e.get('emphasis','A STEP FURTHER.'),560,68,LIME,True); return im
RENDERERS={'question':question,'definition':definition,'concept':concept,'tools':tools,'example_cards':tools,'comparison':comparison,'process':process,'list':list_scene,'before_after':before_after,'takeaway':takeaway,'conclusion':conclusion,'shift':shift}
def render_scene(scene_id,event=None,t=0.0):
 event=dict(event or {})
 if scene_id not in RENDERERS: raise KeyError(f'No renderer registered for NEXORA scene: {scene_id}')
 return RENDERERS[scene_id](event,t)
