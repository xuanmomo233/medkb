# -*- coding: utf-8 -*-
"""医学知识库 学习工具 服务端
用法: python server.py  →  http://127.0.0.1:8820
"""
import json, os, re, sqlite3, time, hashlib
import urllib.request, urllib.parse
import markdown
from flask import Flask, jsonify, request, send_file, Response

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'kb.db')
app = Flask(__name__, static_folder=None)  # 不暴露目录：避免把 kb.db/脚本当静态文件发出去

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

# 启动时自建打卡/设置表（幂等）
_con0 = db()
_con0.execute('CREATE TABLE IF NOT EXISTS checkins(uid INTEGER DEFAULT 0, day TEXT, ts REAL, PRIMARY KEY(uid,day))')
_con0.execute('CREATE TABLE IF NOT EXISTS settings(uid INTEGER DEFAULT 0, k TEXT, v TEXT DEFAULT "", PRIMARY KEY(uid,k))')
_con0.commit()
_con0.close()

# 考点关键词标记（注意 \w 在 Unicode 模式含中文，不能做边界守卫）
_KW = re.compile(
    r'(首选|金标准|(?<![明未])确诊(?!断)|最可能|禁忌|禁用|(?<![非不])特征性'
    r'|(?<!非)特异性|标志物|(?<!不)典型表现|必须|不可)')
_YR = re.compile(r'(?<=[（(])(?:19|20)\d{2}(?:[,、．](?:19|20)\d{2})*(?=[)）])')
_STAR = re.compile(r'★+')

def md(s):
    if not s:
        return ''
    lines = []
    in_table = False
    for ln in s.split('\n'):
        if '](' not in ln:  # 保护链接语法不被标记污染
            ln = _STAR.sub(r'<span class="ex">\g<0></span>', ln)
            ln = _YR.sub(r'<span class="yr">\g<0></span>', ln)
            ln = _KW.sub(r'<mark class="kw">\1</mark>', ln)
        stripped = ln.strip()
        # 表格行归一化：剥离列表前缀、孤立单管道行丢弃、行尾多余 | 收敛
        tbl = re.sub(r'^[-*•]\s+', '', stripped)
        if tbl == '|':
            continue
        if tbl.startswith('|') and tbl.endswith('|') and tbl.count('|') >= 2:
            if not in_table and lines and lines[-1].strip() != '':
                lines.append('')
            in_table = True
            lines.append(re.sub(r'\|+$', '|', tbl))
            continue
        if in_table and stripped:
            lines.append('')   # 表格块结束补空行
        in_table = False
        lines.append(ln)
    html = markdown.markdown('\n'.join(lines), extensions=['tables'])
    html = re.sub(r'<!--.*?-->', '', html)
    # markdown 未能成对的 ** 残留 → 直接清除（医学文本无合法 ** 用法）
    html = html.replace('**', '')
    # ixunke CDN 有 JS 反爬：图走本端代理（自动带 tads 参数 + 磁盘缓存）
    html = re.sub(r'src="(https?://[^"]*ixunke\.com/[^"]+)"',
                  lambda m: 'src="/img_proxy?u=' + urllib.parse.quote(m.group(1), safe='') + '"',
                  html)
    return html

# ---------------- 页面 ----------------
@app.route('/')
def index():
    return send_file(os.path.join(BASE, 'app.html'))

# ---------------- 目录树 ----------------
@app.route('/api/tree')
def tree():
    con = db()
    out = {'导图': [], '知识点': [], '题库': []}
    for r in con.execute("SELECT subj, title, id, kind FROM chapters ORDER BY subj, title"):
        key = '导图' if r['kind'] == 'mm' else '知识点'
        out[key].append({'id': r['id'], 'subj': r['subj'], 'title': r['title']})
    # 题库章节：按 subjdir 分组
    for r in con.execute("SELECT DISTINCT chapter, subjdir FROM questions ORDER BY subjdir, chapter"):
        out['题库'].append({'chapter': r['chapter'], 'subjdir': r['subjdir']})
    return jsonify(out)

# ---------------- 浏览 ----------------
def split_fm(content):
    """拆分 YAML front-matter 元信息 + 去掉重复的考频引用行"""
    meta = {}
    body = content or ''
    if body.startswith('---'):
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', body, re.S)
        if m:
            for ln in m.group(1).split('\n'):
                if ':' in ln:
                    k, v = ln.split(':', 1)
                    meta[k.strip()] = v.strip().strip('[]')
            body = body[m.end():]
    # 正文顶部的 "> 考频：…｜学科：…" 引用与 meta 重复，移除
    body = re.sub(r'^>[^\n]*考频[^\n]*\n?', '', body, count=1, flags=re.M)
    return meta, body

@app.route('/api/chapter')
def chapter():
    cid = int(request.args['id'])
    con = db()
    r = con.execute('SELECT * FROM chapters WHERE id=?', (cid,)).fetchone()
    pages = [int(x) for x in re.findall(r'page_(\d+)', r['content'] or '')]
    meta, body = split_fm(r['content'])
    return jsonify({'title': r['title'], 'subj': r['subj'],
                    'html': md(body), 'src': r['srcfile'], 'meta': meta,
                    'pages': sorted(set(pages))})

@app.route('/img/<name>')
def img(name):
    if not re.fullmatch(r'page_\d+\.webp', name):
        return '', 404
    return send_file(os.path.join(BASE, 'img', name), mimetype='image/webp')

IMG_CACHE = os.path.join(BASE, 'imgcache')
os.makedirs(IMG_CACHE, exist_ok=True)

@app.route('/img_proxy')
def img_proxy():
    """白名单图床代理：ixunke CDN 有 JS 反爬，带 tads 参数即可直出；磁盘缓存"""
    u = request.args.get('u', '')
    if not u.startswith('http') or 'ixunke.com' not in u:
        return 'forbidden', 403
    h = hashlib.sha1(u.encode()).hexdigest()[:16]
    ext = '.png' if '.png' in u.lower() else ('.webp' if '.webp' in u.lower() else '.jpg')
    fp = os.path.join(IMG_CACHE, h + ext)
    if not os.path.exists(fp):
        try:
            sep = '&' if '?' in u else '?'
            req = urllib.request.Request(u + sep + 'tads=1',
                                         headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=20).read()
            if data[:1] == b'<':   # 仍是挑战页 → 不缓存
                return Response(data, mimetype='text/html')
            open(fp, 'wb').write(data)
        except Exception as e:
            return str(e), 502
    return send_file(fp)

# ---------------- 搜索 ----------------
@app.route('/api/search')
def search():
    q = request.args.get('q', '').strip()
    kind = request.args.get('kind', '')
    if not q:
        return jsonify([])
    con = db()
    rows = []
    if len(q) >= 3:
        # trigram FTS
        sql = '''SELECT d.kind, d.ref_id, d.title, snippet(fts,0,'【','】','…',20) snip
                 FROM fts JOIN docs d ON d.id=fts.rowid WHERE fts MATCH ? LIMIT 200'''
        try:
            rows = [dict(r) for r in con.execute(sql, ('"%s"' % q.replace('"', '""'),))]
        except sqlite3.OperationalError:
            rows = []
    else:
        # 短词用 LIKE
        pat = '%' + q + '%'
        for r in con.execute('SELECT id, chapter, stem FROM questions WHERE stem LIKE ? OR analysis LIKE ? LIMIT 100', (pat, pat)):
            rows.append({'kind': 'q', 'ref_id': r['id'], 'title': r['chapter'], 'snip': r['stem'][:60]})
        for r in con.execute('SELECT id, term, body, subj FROM kp_items WHERE term LIKE ? OR body LIKE ? LIMIT 100', (pat, pat)):
            rows.append({'kind': 'k', 'ref_id': r['id'], 'title': r['subj'] + '·' + r['term'], 'snip': r['body'][:80]})
        for r in con.execute('SELECT id, title, subj FROM chapters WHERE content LIKE ? LIMIT 50', (pat,)):
            rows.append({'kind': 'c', 'ref_id': r['id'], 'title': r['subj'] + '·' + r['title'], 'snip': ''})
    if kind:
        rows = [r for r in rows if r['kind'] == kind]
    # 标注各科已学情况
    for r in rows:
        p = con.execute('SELECT state, starred FROM progress WHERE kind=? AND ref=?',
                        (r['kind'], str(r['ref_id']))).fetchone()
        r['state'] = p['state'] if p else ''
        r['starred'] = p['starred'] if p else 0
    return jsonify(rows[:200])

# ---------------- 刷题 ----------------
@app.route('/api/quiz')
def quiz():
    con = db()
    where, args = [], []
    if request.args.get('subjdir'):
        where.append('subjdir=?'); args.append(request.args['subjdir'])
    if request.args.get('chapter'):
        where.append('chapter=?'); args.append(request.args['chapter'])
    if request.args.get('system'):
        where.append('system=?'); args.append(request.args['system'])
    if request.args.get('qtype'):
        where.append('qtype=?'); args.append(request.args['qtype'])
    if request.args.get('bank'):
        where.append('bank=?'); args.append(request.args['bank'])
    if request.args.get('bankgrp'):
        where.append('bankgrp=?'); args.append(request.args['bankgrp'])
    if request.args.get('qids'):
        qlist = [x for x in re.split(r'[,\s]+', request.args['qids']) if x]
        where.append('qid IN (%s)' % ','.join('?' * len(qlist)))
        args += qlist
    if request.args.get('ids'):
        idlist = [x for x in re.split(r'[,\s]+', request.args['ids']) if x]
        where.append('id IN (%s)' % ','.join('?' * len(idlist)))
        args += idlist
    if request.args.get('starred'):
        where.append('CAST(id AS TEXT) IN (SELECT ref FROM progress WHERE kind=\'q\' AND starred=1)')
    if request.args.get('wrong'):
        where.append('CAST(id AS TEXT) IN (SELECT ref FROM progress WHERE kind=\'q\' AND state=\'again\')')
    if request.args.get('due'):
        where.append("CAST(id AS TEXT) IN (SELECT ref FROM progress WHERE kind='q' AND due>0 AND due<?)")
        args.append(time.time())
    sql = 'SELECT * FROM questions' + (' WHERE ' + ' AND '.join(where) if where else '')
    if request.args.get('rand'):
        sql += ' ORDER BY RANDOM() LIMIT 120'
    else:
        sql += ' ORDER BY id'
        if not request.args.get('ids'):
            sql += ' LIMIT 400'
    rows = list(con.execute(sql, args))
    idrefs = [str(r['id']) for r in rows]
    prog = {}
    if idrefs:
        ph = ','.join('?' * len(idrefs))
        for p in con.execute(f'SELECT ref, state, starred FROM progress WHERE kind=\'q\' AND ref IN ({ph})', idrefs):
            prog[p['ref']] = p
    lite = bool(request.args.get('lite'))
    out = []
    for r in rows:
        p = prog.get(str(r['id']))
        out.append({'id': r['id'], 'qid': r['qid'], 'chapter': r['chapter'],
                    'stem': md(r['stem']), 'options': [md(o) for o in json.loads(r['options'] or '[]')],
                    'answer': r['answer'], 'analysis': '' if lite else md(r['analysis']),
                    'parent': md(r['parent']), 'meta': r['meta'], 'src': r['srcfile'],
                    'qtype': r['qtype'], 'system': r['system'], 'bank': r['bank'],
                    'state': p['state'] if p else '', 'starred': p['starred'] if p else 0})
    return jsonify(out)

@app.route('/api/q_full')
def q_full():
    rid = int(request.args['id'])
    con = db()
    r = con.execute('SELECT id, answer, analysis FROM questions WHERE id=?', (rid,)).fetchone()
    if not r:
        return jsonify({'err': 'not found'}), 404
    p = con.execute('SELECT state, starred FROM progress WHERE kind=\'q\' AND ref=?', (str(rid),)).fetchone()
    return jsonify({'id': rid, 'answer': r['answer'], 'analysis': md(r['analysis']),
                    'state': p['state'] if p else '', 'starred': p['starred'] if p else 0})

@app.route('/api/facets')
def facets():
    con = db()
    return jsonify({
        'system': [r[0] for r in con.execute('SELECT DISTINCT system FROM questions ORDER BY system')],
        'qtype': [r[0] for r in con.execute('SELECT DISTINCT qtype FROM questions ORDER BY qtype')],
        'bank': [r[0] for r in con.execute('SELECT DISTINCT bank FROM questions ORDER BY bank')],
        'bankgrp': [r[0] for r in con.execute('SELECT DISTINCT bankgrp FROM questions ORDER BY bankgrp')],
        'subjdir': [r[0] for r in con.execute('SELECT DISTINCT subjdir FROM questions ORDER BY subjdir')],
    })

# ---------------- 背卡 ----------------
_TAG = re.compile(r'（(重复[^）]*|争议[^）]*|易错[^）]*|口诀[^）]*|正确率低[^）]*|死记[^）]*|高频[^）]*)）')

def _split_semi(b):
    """按 ； 拆分，但跳过 **...** 加粗区内部（避免砍断加粗）"""
    parts, cur, bold, i = [], [], False, 0
    while i < len(b):
        if b[i:i+2] == '**':
            bold = not bold; cur.append('**'); i += 2; continue
        if b[i] == '；' and not bold:
            parts.append(''.join(cur)); cur = []; i += 1; continue
        cur.append(b[i]); i += 1
    parts.append(''.join(cur))
    return parts

def card_md(body):
    """考点卡正文排版：清残留标记、分号拆列表行、括号提示转小标签"""
    b = re.sub(r'`', '', body or '').strip()
    b = _TAG.sub(r'<span class="tag">\1</span>', b)
    if '；' in b:
        parts = [p.strip().rstrip('；') for p in _split_semi(b) if p.strip()]
        if len(parts) >= 3:
            b = '\n'.join('- ' + p for p in parts)
    return md(b)

@app.route('/api/cards')
def cards():
    con = db()
    where, args = [], []
    if request.args.get('subj'):
        where.append('subj_real=?'); args.append(request.args['subj'])
    if request.args.get('part'):
        where.append('part=?'); args.append(request.args['part'])
    if request.args.get('ids'):
        idlist = [x for x in re.split(r'[,\s]+', request.args['ids']) if x]
        where.append('id IN (%s)' % ','.join('?' * len(idlist)))
        args += idlist
    if request.args.get('starred'):
        where.append("CAST(id AS TEXT) IN (SELECT ref FROM progress WHERE kind='k' AND starred=1)")
    if request.args.get('due'):
        where.append("CAST(id AS TEXT) IN (SELECT ref FROM progress WHERE kind='k' AND due>0 AND due<?)")
        args.append(time.time())
    sql = 'SELECT * FROM kp_items' + (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY id LIMIT 500'
    out = []
    for r in con.execute(sql, args):
        p = con.execute("SELECT state, starred FROM progress WHERE kind='k' AND ref=?", (str(r['id']),)).fetchone()
        out.append({'id': r['id'], 'subj': r['subj_real'], 'part': r['part'], 'section': r['section'],
                    'term': r['term'], 'hint': r['hint'] if 'hint' in r.keys() else '',
                    'body': card_md(r['body']), 'qids': r['qids'], 'src': r['srcfile'],
                    'state': p['state'] if p else '', 'starred': p['starred'] if p else 0})
    return jsonify(out)

@app.route('/api/kp_index')
def kp_index():
    con = db()
    rows = con.execute('''SELECT subj_real subj, part, COUNT(*) n,
        GROUP_CONCAT(DISTINCT substr(section,1,18)) secs
        FROM kp_items GROUP BY subj_real, part ORDER BY subj_real, part''').fetchall()
    out = []
    for r in rows:
        label = r['part']  # 文件名即主题名（如 01-呼吸系统疾病）
        out.append({'subj': r['subj'], 'part': r['part'], 'n': r['n'], 'label': label})
    return jsonify(out)

# ---------------- 标记/进度 ----------------
SM2 = {'again': 0, 'hard': 1, 'good': 2}

@app.route('/api/mark', methods=['POST'])
def mark():
    d = request.json
    kind, ref, rating = d['kind'], str(d['ref']), d.get('rating')  # again/hard/good/star/unstar/none
    con = db()
    p = con.execute('SELECT * FROM progress WHERE kind=? AND ref=?', (kind, ref)).fetchone()
    now = time.time()
    if rating == 'star':
        if p:
            con.execute('UPDATE progress SET starred=1 WHERE kind=? AND ref=?', (kind, ref))
        else:
            con.execute('INSERT INTO progress(kind,ref,starred,last_ts) VALUES(?,?,1,?)', (kind, ref, now))
    elif rating == 'unstar':
        if p:
            con.execute('UPDATE progress SET starred=0 WHERE kind=? AND ref=?', (kind, ref))
    elif rating in SM2:
        reps = p['reps'] if p else 0
        ease = p['ease'] if p else 2.5
        ivl = p['interval_d'] if p else 0
        if rating == 'again':
            reps, ivl = 0, 0.02   # ~30分钟
            ease = max(1.3, ease - 0.2)
        elif rating == 'hard':
            reps += 1
            ivl = 1 if ivl < 0.5 else ivl * 1.2
            ease = max(1.3, ease - 0.15)
        else:  # good
            reps += 1
            ivl = 1 if reps <= 1 else (3 if reps == 2 else ivl * ease)
            ease = ease + 0.05
        due = now + ivl * 86400
        con.execute('''INSERT INTO progress(kind,ref,reps,ease,interval_d,due,state,last_ts,starred)
                       VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(kind,ref) DO UPDATE SET
                       reps=excluded.reps, ease=excluded.ease, interval_d=excluded.interval_d,
                       due=excluded.due, state=excluded.state, last_ts=excluded.last_ts''',
                    (kind, ref, reps, round(ease, 2), round(ivl, 3), due, rating, now,
                     p['starred'] if p else 0))
    con.commit()
    return jsonify({'ok': True})

# ---------------- 打卡 / 目标 / 日历 ----------------
def day_str(ts=None):
    return time.strftime('%Y-%m-%d', time.localtime(ts or time.time()))

def calc_streak(con, uid=0):
    days = {r['day'] for r in con.execute('SELECT day FROM checkins WHERE uid=?', (uid,))}
    streak = 0
    import datetime
    cur = datetime.date.fromisoformat(day_str())
    if day_str() not in days:
        cur -= datetime.timedelta(days=1)
    while cur.isoformat() in days:
        streak += 1
        cur -= datetime.timedelta(days=1)
    return streak

def get_setting(con, k, default='', uid=0):
    r = con.execute('SELECT v FROM settings WHERE uid=? AND k=?', (uid, k)).fetchone()
    return r['v'] if r else default

@app.route('/api/checkin', methods=['POST'])
def checkin():
    con = db()
    con.execute('INSERT OR IGNORE INTO checkins(uid,day,ts) VALUES(?,?,?)',
                (0, day_str(), time.time()))
    con.commit()
    return jsonify({'ok': True, 'streak': calc_streak(con)})

@app.route('/api/calendar')
def calendar():
    ym = request.args.get('ym', day_str()[:7])
    con = db()
    rows = con.execute("SELECT day FROM checkins WHERE uid=0 AND day LIKE ? ORDER BY day",
                       (ym + '-%',)).fetchall()
    return jsonify({'days': [r['day'][8:] for r in rows],
                    'streak': calc_streak(con)})

@app.route('/api/goal', methods=['GET', 'POST'])
def goal():
    con = db()
    if request.method == 'POST':
        v = int(request.json.get('target') or 30)
        con.execute('INSERT INTO settings(uid,k,v) VALUES(0,?,?) ON CONFLICT(uid,k) DO UPDATE SET v=excluded.v',
                    ('goal', str(v)))
        con.commit()
    return jsonify({'target': int(get_setting(con, 'goal', '30'))})

@app.route('/api/exam', methods=['GET', 'POST'])
def exam():
    con = db()
    if request.method == 'POST':
        v = re.sub(r'[^\d-]', '', request.json.get('date') or '')[:10]
        con.execute('INSERT INTO settings(uid,k,v) VALUES(0,?,?) ON CONFLICT(uid,k) DO UPDATE SET v=excluded.v',
                    ('exam_date', v))
        con.commit()
    return jsonify({'date': get_setting(con, 'exam_date', '2026-12-19')})

# ---------------- 复习队列/统计 ----------------
@app.route('/api/due')
def due():
    con = db()
    now = time.time()
    out = []
    for r in con.execute('SELECT kind, ref FROM progress WHERE due>0 AND due<=? ORDER BY due LIMIT 300', (now,)):
        out.append({'kind': r['kind'], 'ref': r['ref']})
    return jsonify(out)

@app.route('/api/stats')
def stats():
    con = db()
    s = {}
    s['questions'] = con.execute('SELECT COUNT(*) c FROM questions').fetchone()['c']
    s['kp_items'] = con.execute('SELECT COUNT(*) c FROM kp_items').fetchone()['c']
    s['chapters'] = con.execute('SELECT COUNT(*) c FROM chapters').fetchone()['c']
    s['marked'] = con.execute('SELECT COUNT(*) c FROM progress').fetchone()['c']
    s['starred'] = con.execute('SELECT COUNT(*) c FROM progress WHERE starred=1').fetchone()['c']
    s['wrong'] = con.execute("SELECT COUNT(*) c FROM progress WHERE state='again'").fetchone()['c']
    s['due'] = con.execute('SELECT COUNT(*) c FROM progress WHERE due>0 AND due<?', (time.time(),)).fetchone()['c']
    s['mastered'] = con.execute("SELECT COUNT(*) c FROM progress WHERE state='good' AND reps>=2").fetchone()['c']
    return jsonify(s)

@app.route('/api/today')
def today():
    """今日任务：到期复习 + 错题 + 收藏"""
    con = db()
    now = time.time()
    out = {'due': [], 'wrong': [], 'starred': []}
    for r in con.execute('SELECT kind, ref FROM progress WHERE due>0 AND due<? ORDER BY due LIMIT 200', (now,)):
        out['due'].append(dict(r))
    for r in con.execute("SELECT kind, ref FROM progress WHERE state='again' LIMIT 200"):
        out['wrong'].append(dict(r))
    for r in con.execute('SELECT kind, ref FROM progress WHERE starred=1 LIMIT 200'):
        out['starred'].append(dict(r))
    # 打卡/目标/倒计时
    import datetime
    daystart = time.mktime(time.strptime(day_str(), '%Y-%m-%d'))
    out['streak'] = calc_streak(con)
    out['checked_today'] = bool(con.execute(
        'SELECT 1 FROM checkins WHERE uid=0 AND day=?', (day_str(),)).fetchone())
    out['goal'] = int(get_setting(con, 'goal', '30'))
    out['done_today'] = con.execute(
        'SELECT COUNT(*) c FROM progress WHERE last_ts>=?', (daystart,)).fetchone()['c']
    try:
        ed = datetime.date.fromisoformat(get_setting(con, 'exam_date', '2026-12-19'))
        out['exam_days'] = (ed - datetime.date.today()).days
        out['exam_date'] = ed.isoformat()
    except Exception:
        out['exam_days'] = None
    return jsonify(out)

if __name__ == '__main__':
    print('知识库学习工具 → http://127.0.0.1:8820')
    app.run('127.0.0.1', 8820, threaded=True)
