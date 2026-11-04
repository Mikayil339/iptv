"""Cache channel logos as repository-owned PNGs; keep a visible fallback on errors."""
import concurrent.futures as futures
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import refresh

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://raw.githubusercontent.com/Mikayil339/iptv/main/'

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=12) as r:
        data=r.read(3_000_001)
        if len(data)>3_000_000:raise ValueError('Logo too large')
        return data

def png(data):
    if data.lstrip().startswith(b'<'):
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('Unsafe SVG declarations')
        root=ET.fromstring(data)
        if not root.tag.endswith('svg'):raise ValueError('Not an SVG')
        for node in root.iter():
            for key,value in list(node.attrib.items()):
                if key.endswith('href') and not value.startswith('#'):del node.attrib[key]
                elif any(not target.strip(" \"'").startswith('#') for target in re.findall(r'url\(([^)]*)\)',value,re.I)):del node.attrib[key]
            if node.tag.endswith('style') and node.text and re.search(r'@import|url\(',node.text,re.I):node.text=''
        import cairosvg
        data=cairosvg.svg2png(bytestring=ET.tostring(root),output_width=256,output_height=256)
    image=Image.open(io.BytesIO(data))
    if image.width*image.height>20_000_000:raise ValueError('Logo dimensions too large')
    image=image.convert('RGBA');image.thumbnail((256,256))
    canvas=Image.new('RGBA',(256,256));canvas.alpha_composite(image,((256-image.width)//2,(256-image.height)//2))
    out=io.BytesIO();canvas.save(out,format='PNG',optimize=True);return out.getvalue()

def fallback(name):
    color=tuple(45+(x%100) for x in hashlib.sha256(name.encode()).digest()[:3])
    im=Image.new('RGB',(256,256),color);draw=ImageDraw.Draw(im)
    label=''.join(re.findall(r'[A-Za-z0-9]',name))[:4].upper() or 'TV'
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    try:font=ImageFont.truetype(font_path,64)
    except OSError:font=ImageFont.load_default(size=64)
    draw.text((128,128),label,font=font,fill='white',anchor='mm')
    out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()

def main():
    entries=refresh.parse((ROOT/'playlist.m3u8').read_text())
    assets=ROOT/'logos';assets.mkdir(exist_ok=True)
    report_path=ROOT/'logo_status.json'
    old=json.loads(report_path.read_text()) if report_path.exists() else {}
    by_id={}
    api_error=None
    try:
        data,_=refresh.fetch('https://iptv-org.github.io/api/logos.json',limit=20_000_000)
        for logo in json.loads(data):by_id.setdefault(logo['channel'].casefold(),[]).append(logo)
    except Exception as e:api_error=str(e)[:160]
    now=dt.datetime.now(dt.timezone.utc);new={}
    def process(entry):
        cid=refresh.identity(entry);previous=old.get('channels',{}).get(cid,{})
        if previous.get('path') and (ROOT/previous['path']).is_file():
            age=(now-dt.datetime.fromisoformat(previous['checked_at'])).total_seconds()
            if age<7*86400 and not previous.get('fallback'):return cid,previous
        choices=sorted(by_id.get({'tv8,5.tr':'tv85.tr'}.get(cid,cid),[]),key=lambda x:(not x.get('in_use',False),x.get('format','').upper()=='SVG',-int(x.get('height') or 0)))
        urls=[x['url'] for x in choices]
        original=refresh.attributes(entry).get('tvg-logo','')
        if original and not original.startswith(BASE):urls.append(original)
        data=None;used=None
        for url in dict.fromkeys(urls):
            try:data=png(get(url));used=url;break
            except Exception:continue
        is_fallback=data is None
        if data is None:
            # Preserve a previously fetched real image during a remote outage.
            if previous.get('path') and not previous.get('fallback') and (ROOT/previous['path']).is_file():return cid,previous
            data=fallback(entry['name'])
        slug=re.sub('[^a-z0-9.-]','-',cid.casefold())[:90]
        path='logos/'+slug+'-'+hashlib.sha256(data).hexdigest()[:12]+'.png'
        (ROOT/path).write_bytes(data)
        return cid,{'path':path,'source':used,'fallback':is_fallback,'checked_at':now.isoformat(timespec='seconds')}
    # One logo fetch per channel even when a feed occurs more than once.
    unique={refresh.identity(e):e for e in entries}
    with futures.ThreadPoolExecutor(max_workers=16) as ex:
        for cid,info in ex.map(process,unique.values()):new[cid]=info
    for entry in entries:
        cid=refresh.identity(entry);entry['attrs']=re.sub(r' tvg-logo="[^"]*"','',entry['attrs'])+' tvg-logo="'+BASE+new[cid]['path']+'"'
    (ROOT/'playlist.m3u8').write_text(refresh.render(entries),encoding='utf-8')
    report={'checked_at':now.isoformat(timespec='seconds'),'metadata_error':api_error,'channels':new}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Logos:',len(new),'real:',sum(not x['fallback'] for x in new.values()),'fallback:',sum(x['fallback'] for x in new.values()))

if __name__=='__main__':main()
