"""Use GitHub Actions OIDC identity; no persistent GitHub or viewer key is needed."""
import json
import base64
import urllib.error
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = 'https://iptv-access-mikayil339.forgivingclay.chatgpt.site'


def identity():
    url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'] + '&' + urlencode({'audience':'iptv-updater'})
    request = urllib.request.Request(url, headers={'Authorization':'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with urllib.request.urlopen(request, timeout=30) as response:
        token = json.load(response)['value']
        claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))
        print('Updater identity:', json.dumps({k:claims.get(k) for k in ['iss','aud','sub','repository','ref','workflow_ref','exp']},sort_keys=True))
        return token


def call(data=None):
    # Tokens are short-lived and never logged or written to disk.
    request = urllib.request.Request(GATEWAY + '/admin/bundle',
        data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None,
        headers={'X-GitHub-OIDC':identity(), 'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        print('Gateway response:', error.code, error.headers.get('Content-Type'), error.read(250).decode('utf-8','replace'))
        raise


def download():
    bundle = call()
    for name, value in [('playlist.m3u8',bundle['playlist']),('sources.json',bundle['config']),('health.json',bundle['health'])]:
        (ROOT/name).write_text(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False), encoding='utf-8')
    (ROOT/'revision.json').write_text(json.dumps({'revision':bundle['revision']}))


def upload():
    revision = json.loads((ROOT/'revision.json').read_text())['revision']
    health = json.loads((ROOT/'health.json').read_text())
    playlist = (ROOT/'playlist.m3u8').read_text()
    channels = health.get('channels',{}).values()
    summary = {'channels':playlist.count('#EXTINF:'),'healthy':sum(x['check']['ok'] for x in channels),
               'replaced':sum(x['status']=='replaced' for x in channels),'checked_at_utc':health['checked_at_utc']}
    result = call({'revision':revision,'playlist':playlist,'config':json.loads((ROOT/'sources.json').read_text()),'health':health,'summary':summary})
    if not result.get('ok'):
        raise RuntimeError('Gateway did not accept update')
    # Only aggregate numbers are committed to the public repository.
    (ROOT/'LAST_RUN.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Protected playlist updated:',summary['channels'],'channels')


if __name__=='__main__':
    import sys
    {'download':download,'upload':upload}[sys.argv[1]]()
