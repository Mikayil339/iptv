"""Select sports channels by channel metadata and feed language."""
import re
from urllib.parse import urlsplit, parse_qs

def channel_id(entry):
    match = re.search(r'tvg-id="([^"]+)"', entry['attrs'])
    return match[1].split('@')[0].casefold() if match else ''

def build_catalog(channels, feeds, languages):
    languages = set(languages)
    feed_languages, per_channel = {}, {}
    for feed in feeds:
        cid = feed['channel'].casefold()
        langs = set(feed.get('languages', []))
        feed_languages[(cid, feed['id'].casefold())] = langs
        per_channel.setdefault(cid, set()).update(langs)
    eligible, countries = set(), {}
    groups = {'AZ':'Azərbaycan', 'TR':'Türkiyə', 'RU':'Rusiya'}
    for channel in channels:
        cid = channel['id'].casefold()
        countries[cid] = groups.get(channel.get('country'), 'Beynəlxalq')
        if channel.get('is_nsfw') or channel.get('closed'):
            continue
        name = channel.get('name', '').casefold()
        if 'sports' not in channel.get('categories', []) and not re.search(r'football|futbol|soccer|футбол', name):
            continue
        if per_channel.get(cid, set()) & languages:
            eligible.add(cid)
    return eligible, feed_languages, per_channel, countries

def allowed_entry(entry, eligible, feed_languages, per_channel, languages):
    match = re.search(r'tvg-id="([^"]+)"', entry['attrs'])
    if not match:
        return False
    cid, _, fid = match[1].casefold().partition('@')
    if cid not in eligible:
        return False
    langs = feed_languages.get((cid, fid), per_channel.get(cid, set()))
    if not langs.intersection(languages):
        return False
    url = urlsplit(entry['url'])
    query = parse_qs(url.query)
    # Do not import leaked account-based IPTV subscriptions.
    if url.username or url.password or {'username','password'} & set(query):
        return False
    if re.search(r'/live/[^/]+/[^/]+/', url.path):
        return False
    return True
