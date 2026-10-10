# -*- coding: utf-8 -*-
"""wcyk API 复刻：token=AES加密(token#ts,'ixunke')+ts 经 b64，作查询参数"""
import urllib.request, urllib.parse, json, time, os, base64
try:
    from Crypto.Cipher import AES
    from Crypto.Hash import MD5
except ImportError:
    from Cryptodome.Cipher import AES
    from Cryptodome.Hash import MD5

BASE = 'https://api.ixunke.cn/xizongcangqiong'
UA = 'Mozilla/5.0 MicroMessenger/7.0.20 MiniProgramEnv/Windows'
TOKEN = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'token.txt')).read().strip()
DIFFER = 0

def _evp(pw, salt):
    d = b''
    while len(d) < 48:
        d += MD5.new((d[-16:] if d else b'') + pw + salt).digest()
    return d[:32], d[32:48]

def cryptojs_encrypt(msg, pw):
    salt = os.urandom(8)
    k, iv = _evp(pw.encode(), salt)
    data = msg.encode()
    pad = 16 - len(data) % 16
    ct = AES.new(k, AES.MODE_CBC, iv).encrypt(data + bytes([pad]) * pad)
    return base64.b64encode(b'Salted__' + salt + ct).decode()

def encode_token(tok=None):
    tok = tok or TOKEN
    ts = int(time.time() * 1000) + DIFFER
    return base64.b64encode(
        (cryptojs_encrypt(f"{tok}#{ts}", 'ixunke') + f"#{ts}").encode()).decode()

def api(path, params=None, method='GET', auth=True):
    params = dict(params or {})
    if auth:
        params['app'] = 'true'
        params['token'] = encode_token()
    url = BASE + path
    data = None
    if method == 'GET' and params:
        url += '?' + urllib.parse.urlencode(params)
    elif params:
        data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        'User-Agent': UA, 'Content-Type': 'application/json',
        'x-platform': 'mp', 'x-systemType': 'android'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

if __name__ == '__main__':
    j = api('/api/question', {'chapterId': 6536})
    print('errno:', j.get('errno'), '| errmsg:', j.get('errmsg'))
    d = j.get('data')
    qs = d if isinstance(d, list) else (d or {}).get('data', [])
    print('questions:', len(qs))
    if qs:
        q = qs[0]
        print('id:', q['id'], '| stem:', (q.get('stem') or '')[:100])
        print('options:', len(q.get('options') or []), '| answer:', str(q.get('answer'))[:60])
