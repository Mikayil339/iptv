"""Read only clear, explicitly before-login public streams from TRT's visitor page."""
import json
import re
MAP={
 'trt1':('TRT1.tr','TRT 1'), 'trt2':('TRT2.tr','TRT 2'),
 'trtbelgesel':('TRTBelgesel.tr','TRT Belgesel'),
 'trtspor':('TRTSpor.tr','TRT Spor'), 'trtsporyildiz':('TRTSporYildiz.tr','TRT Spor Yıldız'),
 'trthaber':('TRTHaber.tr','TRT Haber'), 'trtcocuk':('TRTCocuk.tr','TRT Çocuk'),
 'trtworld':('TRTWorld.tr','TRT World'), 'trtmuzik':('TRTMuzik.tr','TRT Müzik'),
 'trtturk':('TRTTurk.tr','TRT Türk'), 'trtavaz':('TRTAvaz.tr','TRT Avaz'),
 'trtkurdi':('TRTKurdi.tr','TRT Kurdî')}

def parse_page(text):
    match=re.search(r'<script[^>]+id=[\"\x27]__NEXT_DATA__[\"\x27][^>]*>(.*?)</script>',text,re.S)
    if not match:raise ValueError('Public TRT stream data unavailable')
    data=json.loads(match[1]);entries=[];seen=set()
    def walk(node):
        if isinstance(node,dict):
            slug=node.get('slug')
            if isinstance(slug,str) and slug in MAP and node.get('loginStatus')=='watched_before_login':
                cid,name=MAP[slug]
                for medium in node.get('media',[]):
                    if not isinstance(medium,dict):continue
                    url=medium.get('url','')
                    if medium.get('type')=='hls' and medium.get('drmSchema')=='clear' and url.startswith('https://') and url not in seen:
                        seen.add(url);entries.append({'attrs':'#EXTINF:-1 tvg-id="'+cid+'" group-title="Türkiyə"',
                          'name':name,'url':url,'options':['#EXTVLCOPT:http-user-agent=Mozilla/5.0','#EXTVLCOPT:http-referrer=https://www.tabii.com/']})
            for value in node.values():walk(value)
        elif isinstance(node,list):
            for value in node:walk(value)
    walk(data);return entries
