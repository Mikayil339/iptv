"""Refresh existing channels from public sources; never remove a channel on failure."""
import concurrent.futures as futures
import datetime as dt
import time
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
    attrs = attributes(entry)
    return attrs.get('source-group', attrs.get('group-title', ''))


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
    started = time.monotonic()
    url, height = entry['url'], 0
    headers = headers_for(entry)
    try:
        for depth in range(4):
            raw, final_url = fetch(url, headers, 1_000_000)
            if not raw.lstrip().startswith(b'#EXTM3U'):
                if depth and raw and not raw.lstrip().lower().startswith((b'<', b'{')):
                    return {'ok': True, 'height': height, 'seconds': round(time.monotonic() - started, 2)}
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
            for key_line in lines:
                if key_line.startswith('#EXT-X-KEY:') and 'METHOD=NONE' not in key_line:
                    method = re.search(r'METHOD=([^,]+)', key_line)
                    key_uri = re.search(r'URI="([^"]+)"', key_line)
                    if not method or method[1] != 'AES-128' or not key_uri:
                        raise ValueError('Unsupported encrypted/DRM stream')
                    key_data, _ = fetch(urljoin(final_url, key_uri[1]), headers, 32)
                    if len(key_data) != 16:
                        raise ValueError('HLS encryption key unavailable')
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
            return {'ok': True, 'height': height, 'seconds': round(time.monotonic() - started, 2)}
        raise ValueError('Too many nested manifests')
    except Exception as error:
        return {'ok': False, 'error': str(error)[:160], 'height': height, 'seconds': round(time.monotonic() - started, 2)}


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
    catalog = None
    if config.get('sports_languages'):
        try:
            from sports_catalog import build_catalog
            channel_data, _ = fetch('https://iptv-org.github.io/api/channels.json', limit=20_000_000)
            feed_data, _ = fetch('https://iptv-org.github.io/api/feeds.json', limit=20_000_000)
            catalog = build_catalog(json.loads(channel_data), json.loads(feed_data), config['sports_languages'])
        except Exception as error:
            errors.append({'source': 'sports metadata', 'error': str(error)[:160]})
    for source in config['playlists']:
        try:
            raw, _ = fetch(source['url'])
            for entry in parse(raw.decode('utf-8-sig')):
                if source.get('only_ids') and identity(entry) not in source['only_ids']:
                    continue
                group = source['group']
                if source.get('sports_only'):
                    if catalog is None:
                        continue
                    from sports_catalog import allowed_entry
                    if not allowed_entry(entry, catalog[0], catalog[1], catalog[2], config['sports_languages']):
                        continue
                    group = catalog[3].get(identity(entry), group)
                entry['attrs'] = re.sub(r' group-title="[^"]*"', '', entry['attrs']) + ' group-title="' + group + '"'
                pool.setdefault((group, identity(entry)), []).append(entry)
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
    sports_ids = set(config.get('sports_ids', []))
    if catalog:
        sports_ids.update(catalog[0])
        # Replace non-target-language international feeds through discovery.
        from sports_catalog import allowed_entry
        current = [entry for entry in current if not (
            attributes(entry).get('group-title') == 'Futbol və idman'
            and country(entry) == 'Beynəlxalq'
            and identity(entry) in catalog[3]
            and not allowed_entry(entry, catalog[0], catalog[1], catalog[2], config['sports_languages'])
        )]
    existing_keys = {(country(e), identity(e)) for e in current}
    additions = []
    for key, candidates in pool.items():
        if key in existing_keys:
            continue
        eligible = []
        for candidate in candidates:
            match = re.search(r'(\d{3,4})p', candidate['name'] + ' ' + candidate['url'])
            quality = int(match[1]) if match else (720 if '@HD' in candidate['attrs'] else 0)
            if quality == 0 or quality >= 720 or identity(candidate) in sports_ids:
                eligible.append((quality, candidate))
        if eligible:
            eligible.sort(key=lambda item: item[0], reverse=True)
            additions.append((key, [item[1] for item in eligible[:3]]))
    def discover(item):
        _, candidates = item
        valid = []
        for candidate in candidates:
            result = probe(candidate)
            if result['ok']:
                match = re.search(r'(\d{3,4})p', candidate['name'])
                height = result.get('height') or (int(match[1]) if match else 0)
                if height >= 720 or identity(candidate) in sports_ids:
                    valid.append((height, result.get('seconds', 99), candidate))
        if not valid:
            return None
        valid.sort(key=lambda item: (-item[0], item[1]))
        return valid[0][2]
    seen_urls = {entry['url'] for entry in current}
    with futures.ThreadPoolExecutor(max_workers=20) as executor:
        for entry in executor.map(discover, additions):
            if entry and entry['url'] not in seen_urls:
                current.append(entry)
                seen_urls.add(entry['url'])
    # Put all approved free sports streams into their own group, without copies.
    for entry in current:
        if identity(entry) in sports_ids:
            group = country(entry)
            entry['attrs'] = re.sub(r' group-title="[^"]*"', '', entry['attrs'])
            if 'source-group=' not in entry['attrs']:
                entry['attrs'] += ' source-group="' + group + '"'
            entry['attrs'] += ' group-title="Futbol və idman"'
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    previous = state.get('channels', {})
    def process(entry):
        key = attributes(entry).get('group-title', '') + ':' + identity(entry)
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
        if not result['ok'] and identity(entry) in config.get('required_channels', []):
            for alternative in alternatives[:8]:
                candidate = clean_candidate(alternative, entry)
                candidate_result = probe(candidate)
                if candidate_result['ok']:
                    entry, result = candidate, candidate_result
                    break
        if result['ok'] and (result.get('height', 0) < 720 or result.get('seconds', 0) > 6):
            for alternative in alternatives[:2]:
                candidate = clean_candidate(alternative, entry)
                candidate_result = probe(candidate)
                if candidate_result['ok'] and candidate_result.get('height', 0) >= 720 and (result.get('height', 0) < 720 or candidate_result.get('seconds', 99) < result.get('seconds', 0)):
                    entry, result = candidate, candidate_result
                    break
        chosen, failures, status, result = select(entry, result, alternatives, count)
        if result.get('ok') and result.get('height'):
            height = result['height']
            chosen = dict(chosen)
            chosen['name'] = re.sub(r'\(\d{3,4}p\)', '(' + str(height) + 'p)', chosen['name'])
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
    from collections import Counter
    counts = dict(Counter(attributes(entry).get('group-title', '') for entry in updated))
    overview = {'channels': len(updated), 'healthy': sum(info['check']['ok'] for info in statuses.values()),
                'replaced': sum(info['status'] == 'replaced' for info in statuses.values()),
                'groups': counts, 'checked_at_utc': now,
                'required_channels': {cid: any(identity(entry) == cid for entry in updated) for cid in config.get('required_channels', [])}}
    (ROOT / 'LAST_RUN.json').write_text(json.dumps(overview, ensure_ascii=False, indent=2) + '\n')
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
