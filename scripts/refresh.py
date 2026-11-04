"""Refresh existing channels from public sources; never remove a channel on failure."""
import concurrent.futures as futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
UA = 'Mozilla/5.0'
TIMEOUT = 12


def split_info(line):
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        if char == ',' and not quoted:
            return line[:i], line[i + 1:].strip()
    raise ValueError('Missing EXTINF name separator')


def parse(text):
    entries, block = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#EXTINF:'):
            block = [line]
        elif block and line.startswith('#'):
            block.append(line)
        elif block and line.startswith(('http://', 'https://')):
            try:
                attrs, name = split_info(block[0])
            except ValueError:
                block = []
                continue
            entries.append({'attrs': attrs, 'name': name, 'options': block[1:], 'url': line})
            block = []
    return entries


def attributes(entry):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', entry['attrs']))


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def identity(entry):
    attrs = attributes(entry)
    channel = attrs.get('tvg-id', '').split('@')[0]
    if channel:
        return channel.casefold()
    name = re.sub(r'\([^)]*\)|\[[^]]*\]|\b(?:HD|FHD|SD|UHD)\b', '', entry['name'], flags=re.I)
    return 'name:' + normalized(name)


def country(entry):
    return attributes(entry).get('group-title', '')


def fetch(url, headers=None, limit=4_000_000):
    if urlsplit(url).scheme not in ('http', 'https'):
        raise ValueError('Unsupported URL scheme')
    request = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read(limit), response.geturl()


def headers_for(entry):
    headers = {}
    for line in entry.get('options', []):
        for key, header in [('http-user-agent', 'User-Agent'), ('http-referrer', 'Referer')]:
            prefix = '#EXTVLCOPT:' + key + '='
            if line.startswith(prefix) and line[len(prefix):] != 'No response':
                headers[header] = line[len(prefix):]
    return headers


def probe(entry):
    """Require a media segment, not merely HTTP 200 or a master manifest."""
    url, height = entry['url'], 0
    headers = headers_for(entry)
    try:
        for depth in range(4):
            raw, final_url = fetch(url, headers, 1_000_000)
            if not raw.lstrip().startswith(b'#EXTM3U'):
                if depth and raw and not raw.lstrip().lower().startswith((b'<', b'{')):
                    return {'ok': True, 'height': height}
                raise ValueError('Not HLS/media data')
            text = raw.decode('utf-8-sig')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            variants = []
            for i, line in enumerate(lines[:-1]):
                if line.startswith('#EXT-X-STREAM-INF:') and not lines[i + 1].startswith('#'):
                    match = re.search(r'RESOLUTION=\d+x(\d+)', line)
                    variants.append((int(match[1]) if match else 0, lines[i + 1]))
            if variants:
                height, child = max(variants)
                url = urljoin(final_url, child)
                continue
            # For fMP4, initialization and a media segment must both be reachable.
            init = re.search(r'#EXT-X-MAP:.*?URI="([^"]+)"', text)
            if init:
                fetch(urljoin(final_url, init[1]), headers, 4096)
            segments = [line for line in lines if not line.startswith('#')]
            if not segments or '#EXTINF:' not in text:
                raise ValueError('No media segments')
            raw, _ = fetch(urljoin(final_url, segments[-1]), headers, 4096)
            if not raw or raw.lstrip().lower().startswith((b'<', b'{', b'#extm3u')):
                raise ValueError('Invalid media segment response')
            return {'ok': True, 'height': height}
        raise ValueError('Too many nested manifests')
    except Exception as error:
        return {'ok': False, 'error': str(error)[:160], 'height': height}


def clean_candidate(candidate, original):
    # Preserve channel identity, logo, country and display name from our playlist.
    return {**original, 'url': candidate['url'], 'options': candidate.get('options', [])}


def select(original, current_result, alternatives, previous_failures, checker=probe):
    if current_result['ok']:
        return original, 0, 'ok', current_result
    failures = previous_failures + 1
    # Retry in the same run before counting a failure.
    retry = checker(original)
    if retry['ok']:
        return original, 0, 'ok_after_retry', retry
    if failures < 2:
        return original, failures, 'retry_next_run', retry
    for candidate in alternatives[:8]:
        candidate = clean_candidate(candidate, original)
        result = checker(candidate)
        if result['ok']:
            return candidate, 0, 'replaced', result
    return original, failures, 'unavailable_kept', retry


def render(entries):
    lines = ['#EXTM3U', '#PLAYLIST:Azərbaycan • Türkiyə • Rusiya']
    for entry in entries:
        lines.append(entry['attrs'] + ',' + entry['name'])
        lines.extend(entry.get('options', []))
        lines.append(entry['url'])
    return '\n'.join(lines) + '\n'


def main():
    config = json.loads((ROOT / 'sources.json').read_text())
    playlist = ROOT / 'playlist.m3u8'
    original_text = playlist.read_text()
    current = parse(original_text)
    if len(current) != sum(line.startswith('#EXTINF:') for line in original_text.splitlines()):
        raise RuntimeError('Invalid local channel metadata; refusing to drop entries')
    if not current:
        raise RuntimeError('Refusing to overwrite an empty/invalid playlist')
    state_path = ROOT / 'health.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    pool = {}
    errors = []
    for source in config['playlists']:
        try:
            raw, _ = fetch(source['url'])
            for entry in parse(raw.decode('utf-8-sig')):
                entry['attrs'] = re.sub(r' group-title="[^"]*"', '', entry['attrs']) + ' group-title="' + source['group'] + '"'
                pool.setdefault((source['group'], identity(entry)), []).append(entry)
        except Exception as error:
            errors.append({'source': source['url'], 'error': str(error)[:160]})
    for webpage in config.get('webpages', []):
        try:
            raw, _ = fetch(webpage['url'])
            text = raw.decode('utf-8', 'replace')
            text = re.sub(r'\\+/', '/', text)
            urls = set(re.findall(r'https://operativmm\.az/tvs/[a-zA-Z0-9_./-]+\.m3u8', text))
            for url in urls:
                slug = urlsplit(url).path.split('/')[2]
                channel = webpage['channels'].get(slug)
                if channel:
                    entry = {'attrs': '#EXTINF:-1 tvg-id="' + channel['id'] + '" group-title="Azərbaycan"',
                             'name': channel['name'], 'url': url,
                             'options': ['#EXTVLCOPT:http-user-agent=Mozilla/5.0']}
                    pool.setdefault(('Azərbaycan', identity(entry)), []).insert(0, entry)
        except Exception as error:
            errors.append({'source': webpage['url'], 'error': str(error)[:160]})
    for entry in config.get('backups', []):
        pool.setdefault((country(entry), identity(entry)), []).insert(0, entry)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    previous = state.get('channels', {})
    def process(entry):
        key = country(entry) + ':' + identity(entry)
        prior = previous.get(key, {})
        # Reset failures when a human changed the stream URL.
        count = prior.get('failures', 0) if prior.get('url') == entry['url'] else 0
        alternatives, seen = [], {entry['url']}
        # Remember discovered backups, including temporary failures.
        candidates = pool.get((country(entry), identity(entry)), []) + prior.get('backups', [])
        for candidate in candidates:
            if candidate['url'] not in seen:
                seen.add(candidate['url']); alternatives.append(candidate)
        def quality(candidate):
            match = re.search(r'(\d{3,4})p', candidate['name'] + ' ' + candidate['url'])
            return int(match[1]) if match else 0
        alternatives.sort(key=quality, reverse=True)
        result = probe(entry)
        chosen, failures, status, result = select(entry, result, alternatives, count)
        cached = [clean_candidate(c, entry) for c in alternatives if c['url'] != chosen['url']][:12]
        if chosen['url'] != entry['url']:
            cached.append(entry)
        return chosen, key, {'name': entry['name'], 'url': chosen['url'], 'failures': failures,
                            'status': status, 'check': result, 'backups': cached[:12]}
    with futures.ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(process, current))
    updated = [item[0] for item in results]
    if len(updated) != len(current):
        raise RuntimeError('Channel count changed unexpectedly')
    statuses = {item[1]: item[2] for item in results}
    state = {'checked_at_utc': now, 'source_errors': errors, 'channels': statuses}
    playlist.write_text(render(updated), encoding='utf-8')
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    rows = ['# Yayım vəziyyəti', '', 'Son yoxlama (UTC): ' + now, '',
            '| Ölkə | Kanal | Vəziyyət | Ardıcıl uğursuz yoxlama |', '|---|---|---|---|']
    for chosen, key, info in results:
        rows.append('| ' + ' | '.join([country(chosen), chosen['name'].replace('|', '/'), info['status'], str(info['failures'])]) + ' |')
    rows += ['', 'Açılmayan kanal silinmir. Əvəzləmə ən azı iki ardıcıl yoxlamadan sonra edilir.',
             'Yoxlama video fraqmentinin alınmasını təsdiqləyir; uzunmüddətli oynatma, səs və coğrafi əlçatanlıq zəmanəti deyil.',
             '', 'Mənbə xətalarının sayı: ' + str(len(errors))]
    (ROOT / 'STATUS.md').write_text('\n'.join(rows) + '\n')
    summary = f"Channels: {len(updated)}; replacements: {sum(x['status'] == 'replaced' for x in statuses.values())}; failing: {sum(x['failures'] > 0 for x in statuses.values())}"
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary + '\n')


if __name__ == '__main__':
    main()
