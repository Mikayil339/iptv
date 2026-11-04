import io
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from PIL import Image
import sports_catalog as s
import update_logos as logos

class CatalogTests(unittest.TestCase):
 def setUp(self):
  channels=[{'id':'Sport.xx','name':'Football TV','categories':['sports'],'country':'GB','is_nsfw':False,'closed':None},{'id':'News.xx','name':'News','categories':['news'],'country':'GB'}]
  feeds=[{'channel':'Sport.xx','id':'English','languages':['eng']},{'channel':'Sport.xx','id':'German','languages':['deu']},{'channel':'News.xx','id':'SD','languages':['eng']}]
  self.catalog=s.build_catalog(channels,feeds,['aze','rus','eng','tur'])
 def e(self,feed,url='https://example.org/live.m3u8'):
  return {'attrs':'#EXTINF:-1 tvg-id="Sport.xx@'+feed+'"','url':url}
 def test_feed_language_is_checked(self):
  c=self.catalog
  self.assertTrue(s.allowed_entry(self.e('English'),c[0],c[1],c[2],['eng']))
  self.assertFalse(s.allowed_entry(self.e('German'),c[0],c[1],c[2],['eng']))
  self.assertNotIn('news.xx',c[0])
 def test_account_urls_are_not_imported(self):
  c=self.catalog
  for url in ['https://user:password@example.org/live.m3u8','https://example.org/get.php?username=a&password=b','https://example.org/live/user/password/1.m3u8']:
   self.assertFalse(s.allowed_entry(self.e('English',url),c[0],c[1],c[2],['eng']))

class LogoTests(unittest.TestCase):
 def test_raster_becomes_square_png(self):
  original=io.BytesIO();Image.new('RGB',(200,100),'red').save(original,format='JPEG')
  result=logos.png(original.getvalue());im=Image.open(io.BytesIO(result));self.assertEqual(im.size,(256,256));self.assertEqual(im.format,'PNG')
 def test_svg_is_converted_without_external_images(self):
  result=logos.png(b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><image href="file:///etc/passwd"/><rect width="40" height="40" fill="red"/></svg>')
  im=Image.open(io.BytesIO(result));self.assertEqual(im.getpixel((128,128))[:3],(255,0,0))
 def test_transparent_logo_is_rejected(self):
  data=io.BytesIO();Image.new('RGBA',(20,20)).save(data,format='PNG')
  with self.assertRaises(ValueError):logos.png(data.getvalue())
 def test_invalid_image_is_not_accepted(self):
  with self.assertRaises(Exception):logos.png(b'<html>Error</html>')
 def test_fallback_is_a_valid_visible_image(self):
  im=Image.open(io.BytesIO(logos.fallback('Test TV')));self.assertEqual(im.size,(256,256));self.assertGreater(len(im.getcolors(65536)),1)

if __name__=='__main__':unittest.main()

class SupplementalLogoTests(unittest.TestCase):
 def test_exact_channel_and_country_are_matched(self):
  tree={'tree':[{'path':'countries/turkey/trt-belgesel-tr.png','type':'blob'},{'path':'countries/united-states/espn-2-us.png','type':'blob'}]}
  idx=logos.supplemental_index(tree)
  self.assertEqual(len(logos.supplemental_urls('trtbelgesel.tr','TRT Belgesel','Türkiyə',idx)),1)
  self.assertEqual(logos.supplemental_urls('trthaber.tr','TRT Haber','Türkiyə',idx),[])

class TRTTests(unittest.TestCase):
 def test_only_public_before_login_clear_hls_is_imported(self):
  import official_trt
  rows=[{'slug':'trtbelgesel','loginStatus':'watched_before_login','media':[{'type':'hls','drmSchema':'clear','url':'https://trt.example.org/master.m3u8'},{'type':'hls','drmSchema':'widevine','url':'https://drm.example.org/master.m3u8'}]},{'slug':'trtspor','loginStatus':'login_required','media':[{'type':'hls','drmSchema':'clear','url':'https://private.example.org/master.m3u8'}]}]
  import json
  page='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(rows)+'</script>'
  entries=official_trt.parse_page(page);self.assertEqual(len(entries),1);self.assertIn('TRTBelgesel.tr',entries[0]['attrs'])
