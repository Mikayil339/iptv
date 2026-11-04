import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import json
spec=importlib.util.spec_from_file_location('refresh',Path(__file__).parents[1]/'scripts/refresh.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class Tests(unittest.TestCase):
 def setUp(self):self.e=r.parse('#EXTM3U\n#EXTINF:-1 tvg-id="TV8,5.tr@HD" group-title="Türkiyə",TV 8.5\nhttps://example.org/live.m3u8\n')[0]
 def test_comma_roundtrip(self):self.assertEqual(r.parse(r.render([self.e])),[self.e])
 def test_free_sports_keep_source_country(self):
  e={**self.e,'attrs':self.e['attrs'].replace('group-title="Türkiyə"','source-group="Türkiyə" group-title="Futbol və idman"')}
  self.assertEqual(r.country(e),'Türkiyə')
 def test_temporary_failure(self):
  e,n,status,_=r.select(self.e,{'ok':False},[],0,lambda _: {'ok':False})
  self.assertEqual((e,n,status),(self.e,1,'retry_next_run'))
 def test_replacement(self):
  alt={**self.e,'url':'https://alt.org/live.m3u8'}
  e,n,status,_=r.select(self.e,{'ok':False},[alt],1,lambda e:{'ok':e['url']==alt['url']})
  self.assertEqual((e['url'],n,status),(alt['url'],0,'replaced'))
 def test_html_is_not_video(self):
  with patch.object(r,'fetch',return_value=(b'<html>error</html>',self.e['url'])):self.assertFalse(r.probe(self.e)['ok'])
 def test_nested_hls_segment(self):
  with patch.object(r,'fetch',side_effect=[(b'#EXTM3U\n#EXT-X-STREAM-INF:RESOLUTION=1280x720\nchild.m3u8\n',self.e['url']),(b'#EXTM3U\n#EXTINF:4,\nsegment.ts\n','https://example.org/child.m3u8'),(b'G'*188,'https://example.org/segment.ts')]):
   x=r.probe(self.e);self.assertTrue(x['ok']);self.assertEqual(x['height'],720)
 def test_source_outage_keeps_all_channels(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'playlist.m3u8').write_text(r.render([self.e]));(p/'sources.json').write_text('{"playlists":[]}')
   with patch.object(r,'ROOT',p),patch.object(r,'probe',return_value={'ok':False}):r.main()
   self.assertEqual(r.parse((p/'playlist.m3u8').read_text()),[self.e])
 def test_malformed_local_playlist_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'playlist.m3u8').write_text('#EXTM3U\n#EXTINF:-1 tvg-id="broken,Name\nhttps://a.org/live.m3u8\n');(p/'sources.json').write_text('{"playlists":[]}')
   with patch.object(r,'ROOT',p):
    with self.assertRaises(RuntimeError):r.main()
if __name__=='__main__':unittest.main()
