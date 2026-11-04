"""Curated cinema discovery with decoded video resolution checks.

Only verified 1080p Russian streams receive the 1080p group. A failed or
lower-resolution existing channel is retained in its country group.
"""
import concurrent.futures as futures
import json
import re
import subprocess
from collections import Counter
from urllib.parse import urljoin
from refresh import ROOT, UA, attributes, country, fetch, identity, parse, probe, render, clean_candidate, headers_for


def set_attr(entry, key, value):
    entry = dict(entry)
    entry['attrs'] = re.sub(r' ' + re.escape(key) + r'="[^"]*"', '', entry['attrs']) + ' ' + key + '="' + value + '"'
    return entry


def decoded_check(entry):
    result = probe(entry)
    if not result['ok']:
        return result
    # A title or even a master manifest can overstate the actual encoded size.
    url = entry['url']
    try:
        for _ in range(4):
            raw, final = fetch(url, headers_for(entry), 1_000_000)
            lines = raw.decode('utf-8-sig').splitlines()
            variants = []
            for i, line in enumerate(lines[:-1]):
                if line.startswith('#EXT-X-STREAM-INF:'):
                    match = re.search(r'RESOLUTION=\d+x(\d+)', line)
                    variants.append((int(match[1]) if match else 0, lines[i + 1].strip()))
            if not variants:
                break
            url = urljoin(final, max(variants)[1])
    except Exception:
        result.update(height=0, resolution_verified=False)
        return result
    args = ['ffprobe', '-v', 'error', '-rw_timeout', '8000000', '-analyzeduration', '2000000', '-probesize', '3000000', '-user_agent', UA]
    headers = headers_for(entry)
    if headers.get('Referer'):
        args += ['-headers', 'Referer: ' + headers['Referer'] + '\r\n']
    args += ['-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', url]
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=25)
        streams = json.loads(completed.stdout).get('streams', [])
        width = max((s.get('width', 0) for s in streams), default=0)
        height = max((s.get('height', 0) for s in streams), default=0)
        result.update(height=height, width=width, resolution_verified=bool(width and height))
    except (subprocess.TimeoutExpired, ValueError, OSError):
        result.update(height=0, resolution_verified=False)
    return result


def qualifies(result, minimum):
    return result.get('ok', False) and result.get('resolution_verified', False) and result.get('height', 0) >= minimum


def classify(entry, result, profile):
    original_country = profile['country']
    entry = set_attr(entry, 'source-group', original_country)
    group = profile['group'] if qualifies(result, profile['min_height']) else original_country
    entry = set_attr(entry, 'group-title', group)
    if result.get('resolution_verified'):
        entry['name'] = re.sub(r'\s*\(\d{3,4}p\)', '', entry['name']) + ' (' + str(result['height']) + 'p)'
    return entry


def main():
    config = json.loads((ROOT / 'cinema.json').read_text())
    current = parse((ROOT / 'playlist.m3u8').read_text())
    profiles = {cid.casefold(): p for p in config['profiles'] for cid in p['ids']}
    pool = {}
    errors = []
    for source in config['sources']:
        try:
            entries = parse(fetch(source['url'])[0].decode('utf-8-sig'))
            for entry in entries:
                mapped = source.get('name_ids', {}).get(entry['name'])
                if mapped:
                    entry = set_attr(entry, 'tvg-id', mapped)
                entry['url'] = entry['url'].split('#', 1)[0]
                cid = identity(entry)
                if cid in profiles and profiles[cid]['country'] == source['country']:
                    pool.setdefault(cid, []).append(entry)
        except Exception as error:
            errors.append({'source': source['url'], 'error': str(error)[:160]})
    for entry in config.get('backups', []):
        pool.setdefault(identity(entry), []).append(entry)
    existing = {identity(e): e for e in current}
    tasks = sorted(set(profiles) & (set(existing) | set(pool)))

    def process(cid):
        profile = profiles[cid]
        original = existing.get(cid)
        candidates = ([original] if original else []) + pool.get(cid, [])
        seen = set()
        last_result = {'ok': False, 'height': 0, 'error': 'No working cinema source'}
        for candidate in candidates:
            key = (candidate['url'], tuple(candidate.get('options', [])))
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 5:
                break
            entry = clean_candidate(candidate, original) if original else dict(candidate)
            result = decoded_check(entry)
            if candidate is original:
                last_result = result
            if qualifies(result, profile['min_height']):
                return cid, classify(entry, result, profile), result
        # Never add a failed candidate, and never discard an existing channel.
        return cid, classify(original, last_result, profile) if original else None, last_result

    with futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process, tasks))
    replacements = {cid: entry for cid, entry, result in results if entry}
    updated = [replacements.pop(identity(e), e) for e in current]
    updated += list(replacements.values())
    (ROOT / 'playlist.m3u8').write_text(render(updated), encoding='utf-8')
    report = {'source_errors': errors, 'channels': {cid: {'name': entry['name'] if entry else cid,
              'group': attributes(entry).get('group-title') if entry else None, 'check': result}
              for cid, entry, result in results}}
    (ROOT / 'cinema_status.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    overview_path = ROOT / 'LAST_RUN.json'
    overview = json.loads(overview_path.read_text()) if overview_path.exists() else {}
    overview.update(channels=len(updated), groups=dict(Counter(attributes(e).get('group-title', '') for e in updated)))
    # Re-key health entries after moving categories, and account for cinema checks.
    health_path = ROOT / 'health.json'
    if health_path.exists():
        health = json.loads(health_path.read_text())
        old = health.get('channels', {})
        checked = {cid: result for cid, entry, result in results if entry}
        by_id = {key.split(':', 1)[-1]: value for key, value in old.items()}
        channels = {}
        for entry in updated:
            cid = identity(entry)
            info = dict(by_id.get(cid, {}))
            info.update(name=entry['name'], url=entry['url'])
            if cid in checked:
                info['check'] = checked[cid]
                info['status'] = 'cinema_verified' if qualifies(checked[cid], profiles[cid]['min_height']) else 'cinema_quality_unavailable'
            channels[attributes(entry).get('group-title', '') + ':' + cid] = info
        health['channels'] = channels
        health_path.write_text(json.dumps(health, ensure_ascii=False, indent=2) + '\n')
        overview['healthy'] = sum(i.get('check', {}).get('ok', False) for i in channels.values())
    overview_path.write_text(json.dumps(overview, ensure_ascii=False, indent=2) + '\n')
    status = ROOT / 'STATUS.md'
    if status.exists():
        text = status.read_text().split('\n## Kino keyfiyyəti')[0]
        text += '\n## Kino keyfiyyəti\n\n1080p Russian Movies yalnız video ölçüsü təsdiqlənən yayımları göstərir. Keyfiyyət düşəndə kanal ölkə qrupunda saxlanılır.\n\n'
        text += '| Kanal | Qrup | Yoxlanmış ölçü |\n|---|---|---|\n'
        for cid, entry, result in results:
            if entry:
                text += '| ' + entry['name'] + ' | ' + attributes(entry)['group-title'] + ' | ' + str(result.get('width', 0)) + '×' + str(result.get('height', 0)) + ' |\n'
        status.write_text(text)
    print(json.dumps(overview['groups'], ensure_ascii=False))


if __name__ == '__main__':
    main()
