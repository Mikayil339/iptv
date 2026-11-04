import importlib.util
from pathlib import Path
import unittest
import tempfile
import json
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('refresh', Path(__file__).parents[1] / 'scripts/refresh.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.e = r.parse('#EXTM3U\n#EXTINF:-1 tvg-id="TV8,5.tr@HD" group-title="Türkiyə",TV 8.5\nhttps://example.org/live.m3u8\n')[0]

    def test_quoted_comma_and_round_trip(self):
        self.assertEqual(self.e['name'], 'TV 8.5')
        self.assertEqual(r.identity(self.e), 'tv8,5.tr')
        self.assertEqual(r.parse(r.render([self.e])), [self.e])

    def test_transient_failure_keeps_channel(self):
        fail = {'ok': False}
        chosen, count, status, _ = r.select(self.e, fail, [], 0, lambda _: fail)
        self.assertEqual((chosen, count, status), (self.e, 1, 'retry_next_run'))

    def test_replacement_preserves_identity_and_country(self):
        alt = {**self.e, 'url': 'https://other.org/live.m3u8'}
        check = lambda e: {'ok': e['url'] == alt['url']}
        chosen, count, status, _ = r.select(self.e, {'ok': False}, [alt], 1, check)
        self.assertEqual((chosen['url'], count, status), (alt['url'], 0, 'replaced'))
        self.assertEqual(chosen['attrs'], self.e['attrs'])

    def test_all_sources_down_never_removes_channel(self):
        chosen, count, status, _ = r.select(self.e, {'ok': False}, [], 5, lambda _: {'ok': False})
        self.assertEqual((chosen, count, status), (self.e, 6, 'unavailable_kept'))

    def test_probe_requires_segment_and_resolves_relative_links(self):
        master = b'#EXTM3U\n#EXT-X-STREAM-INF:RESOLUTION=1280x720\nchild.m3u8\n'
        media = b'#EXTM3U\n#EXTINF:4,\nsegment.ts\n'
        with patch.object(r, 'fetch', side_effect=[(master, self.e['url']), (media, 'https://example.org/child.m3u8'), (b'G' * 188, 'https://example.org/segment.ts')]) as mock:
            self.assertEqual(r.probe(self.e), {'ok': True, 'height': 720})
            self.assertEqual(mock.call_args.args[0], 'https://example.org/segment.ts')
        with patch.object(r, 'fetch', return_value=(b'<html>Error</html>', self.e['url'])):
            self.assertFalse(r.probe(self.e)['ok'])

    def test_full_run_keeps_all_channels_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = r.render([self.e])
            (root / 'playlist.m3u8').write_text(original)
            (root / 'sources.json').write_text(json.dumps({'playlists': [{'url': 'https://source.invalid', 'group': 'Türkiyə'}]}))
            with patch.object(r, 'ROOT', root), patch.object(r, 'fetch', side_effect=OSError('source down')), patch.object(r, 'probe', return_value={'ok': False}):
                r.main()
            self.assertEqual(r.parse((root / 'playlist.m3u8').read_text()), [self.e])
            state = json.loads((root / 'health.json').read_text())
            self.assertEqual(len(state['source_errors']), 1)
            self.assertEqual(next(iter(state['channels'].values()))['failures'], 1)
            self.assertTrue((root / 'STATUS.md').exists())

if __name__ == '__main__':
    unittest.main()
