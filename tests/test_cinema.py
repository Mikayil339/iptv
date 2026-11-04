import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from refresh_cinema import classify, qualifies
from refresh import attributes, country

class CinemaQualityTests(unittest.TestCase):
    def test_manifest_or_title_alone_is_not_1080_proof(self):
        self.assertFalse(qualifies({'ok': True, 'height': 1080}, 1080))
        self.assertFalse(qualifies({'ok': False, 'resolution_verified': True, 'height': 1080}, 1080))

    def test_downgrade_returns_channel_to_country_without_removal(self):
        p = {'country': 'Rusiya', 'group': '1080p Russian Movies', 'min_height': 1080}
        entry = {'attrs': '#EXTINF:-1 tvg-id="Example.ru" group-title="1080p Russian Movies"', 'name': 'Example (1080p)', 'url': 'https://example.com/live.m3u8'}
        result = {'ok': True, 'resolution_verified': True, 'height': 576}
        downgraded = classify(entry, result, p)
        self.assertEqual(attributes(downgraded)['group-title'], 'Rusiya')
        self.assertEqual(downgraded['url'], entry['url'])
        self.assertIn('(576p)', downgraded['name'])
        result['height'] = 1080
        restored = classify(downgraded, result, p)
        self.assertEqual(attributes(restored)['group-title'], p['group'])
        self.assertEqual(country(restored), 'Rusiya')
