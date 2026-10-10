# -*- coding: utf-8 -*-
"""按思维导图知识点重分类 questions.system → '学科·章·节'
算法：倒排索引。节术语→2gram shingles 建索引；题目文本切 shingle 反查候选术语→验证→加权打分。
用法: python3 reclassify_system.py [--sample 500] [--apply]
"""
import json, os, re, sys
from collections import Counter, defaultdict
import psycopg2, psycopg2.extras

DB = 'dbname=medkb user=user_DeDhkF password=password_6XeeG8 host=127.0.0.1'

SUBJ_HINT = [
    ('生理学', '生理'), ('生物化学', '生化|生物化学|分子生物|合成代谢|分解代谢'),
    ('病理学', '病理'), ('内科学', '内科'), ('外科学', '外科'), ('诊断学', '诊断'),
    ('医学人文', '人文|伦理|医德|医患|心理|法规'), ('政治', '政治|肖秀荣|肖\d|腿四|涛|毛中特|马原'),
    ('英语', '英语|每日一句|阅读|作文'),
]
ALL_SUBJS = ['生理学', '生物化学', '病理学', '内科学', '外科学']
HUM = re.compile(r'知情同意|伦理|医患|医德|脑死亡|移植|医疗事故|医师法|道德|临终|处方|献血|器官')
HUM2 = re.compile(r'医学|患者|病人')

def subj_hint(bank, chapter, text):
    t = (bank or '') + ' ' + (chapter or '')
    hits = {s for s, pat in SUBJ_HINT if re.search(pat, t)}
    # 题目文本强人文特征 → 直接归人文（导图无人文章节，避免误入临床学科）
    if len(HUM.findall(text)) >= 2 and not HUM2.search(bank or ''):
        return {'医学人文'}
    if hits:
        return hits - {'医学人文', '政治', '英语'} or hits
    return set(ALL_SUBJS)

_WORD = re.compile(r'[一-龥A-Za-z0-9α-ωΑ-ΩⅠ-ⅺ]{2,}')

def parse_chapter(content):
    """→ [(节名, 节文本)]，## 为节边界"""
    secs, cur_name, cur_lines = [], '导语', []
    def flush():
        secs.append((cur_name, '\n'.join(cur_lines)))
    for ln in (content or '').split('\n'):
        m = re.match(r'^##\s+(.+?)(?:（[^）]*）)?\s*$', ln.strip())
        if m:
            flush(); cur_name, cur_lines = m.group(1).strip(), []
            continue
        cur_lines.append(ln)
    flush()
    return secs

def shingles(t):
    """词→2gram 集合（2字词=自身）"""
    if len(t) <= 2:
        return {t}
    return {t[i:i + 2] for i in range(len(t) - 1)}

def main():
    sample, apply_ = None, '--apply' in sys.argv
    for i, a in enumerate(sys.argv):
        if a == '--sample' and i + 1 < len(sys.argv):
            sample = int(sys.argv[i + 1])
    con = psycopg2.connect(DB, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = con.cursor()

    # ---- 导图 → 节术语 ----
    cur.execute("SELECT id, subj, title, content FROM chapters WHERE kind='mm' ORDER BY id")
    chs = cur.fetchall()
    print('导图章节:', len(chs))
    secs = []            # (subj, title, secname, terms:set)
    for r in chs:
        title = re.sub(r'^\d+-', '', r['title'])
        for secname, body in parse_chapter(r['content']):
            secname = re.sub(r'[★☆\s]+$', '', secname).strip()
            terms = set(_WORD.findall(re.sub(r'[#*>\-`|（）()\[\]【】《》，。；：:、！？!?~％%""'',.<>+＝=×÷/…～·\s]', ' ', body)))
            # 标题词也入术语（权重后面另加）
            secs.append({'subj': r['subj'], 'title': title, 'sec': secname,
                         'terms': terms, 'head': set(_WORD.findall(secname))})

    # DF：术语出现在多少节里 → idf
    df = Counter()
    for s in secs:
        for t in s['terms']:
            df[t] += 1
    # 倒排：shingle → {terms}；term → [(secidx)]
    inv = defaultdict(set)
    term_secs = defaultdict(list)
    live_terms = {}    # term → idf（DF≤60 才用，太常见的不做硬锚）
    for si, s in enumerate(secs):
        for t in s['terms']:
            # DF>20 的通用词不入索引（大词表章节不再靠"什么都沾一点"取胜）
            if len(t) < 2 or df[t] > 20:
                continue
            live_terms[t] = 2.2 / (1 + df[t] * 0.3)
            term_secs[t].append(si)
            for g in shingles(t):
                inv[g].add(t)
    print('节数:', len(secs), '| 术语数:', len(live_terms), '| 倒排键:', len(inv))

    # ---- 题目 ----
    cur.execute('SELECT id, qid, bank, chapter, stem, options, analysis, parent, system FROM questions')
    qs = cur.fetchall()
    print('题目:', len(qs))
    rows = qs[:sample] if sample else qs
    stats = Counter()
    updates, examples = [], []
    for q in rows:
        try:
            opts = ' '.join(json.loads(q['options'] or '[]'))
        except Exception:
            opts = ''
        text = ' '.join(x for x in [q['stem'], q['analysis'], opts, q['parent']] if x)
        cands = subj_hint(q['bank'], q['chapter'], text)
        # 文本 shingles → 命中术语 → 按节累计
        tset = set()
        ttext = re.sub(r'\s', '', text)
        for i in range(len(ttext) - 1):
            tset.add(ttext[i:i + 2])
        hit_terms = set()
        for g in tset:
            hit_terms |= inv.get(g, set())
        scores = defaultdict(float)
        hitn = defaultdict(int)          # 每节命中的不同术语数
        for t in hit_terms:
            if t in ttext:
                w = live_terms[t]
                for si in term_secs[t]:
                    scores[si] += w
                    hitn[si] += 1
        for si in list(scores):
            h = secs[si]
            # 词表过大仅做温和衰减（通用词已被 DF 阈值剔除）
            scores[si] = scores[si] / (1 + len(h['terms']) / 80.0)
            if any(w in ttext for w in h['head']):
                scores[si] += 0.8
        # 只在候选学科里选（记录前两名做歧义判定）
        best, best2 = None, None
        for si, sc in scores.items():
            if secs[si]['subj'] not in cands:
                continue
            if best is None or sc > best[1]:
                best2, best = best, (si, sc)
            elif best2 is None or sc > best2[1]:
                best2 = (si, sc)
        # 三级要求：分够高 + 命中≥3个不同术语 + 不是导语
        # 且第一名≥第二名 1.4 倍（否则章节判不准，降回二级）
        top = secs[best[0]] if best else None
        decisive = best2 is None or (best[1] >= best2[1] * 1.4)
        if best and best[1] >= 4.0 and hitn[best[0]] >= 3 \
                and top['sec'] != '导语' and decisive:
            new = f"{top['subj']}·{top['title']}·{top['sec']}"
            stats['3级'] += 1
        elif best and best[1] >= 2.8:
            s = secs[best[0]]
            new = f"{s['subj']}·{s['title']}"
            stats['2级'] += 1
        elif len(cands) == 1:
            new = next(iter(cands))
            stats['1级'] += 1
        else:
            new = '其他'
            stats['其他'] += 1
        if new != (q['system'] or ''):
            updates.append((new, q['id']))
            if sample and len(examples) < 18:
                examples.append((q['qid'], (q['stem'] or '')[:45], new, round(best[1], 1) if best else 0))
    for e in examples:
        print(' ', e)
    print('分布:', dict(stats), '| 需更新:', len(updates))
    if apply_ and updates:
        cur.executemany('UPDATE questions SET system=%s WHERE id=%s', updates)
        con.commit()
        print('applied:', len(updates))

    # ---- 题库系分类（天门·年份 等）按 bank 一次更新 ----
    if apply_:
        sys.path.insert(0, '/opt/medkb')
        from wcyk_sync import bankgrp
        cur.execute('ALTER TABLE questions ADD COLUMN IF NOT EXISTS bankgrp text')
        con.commit()
        cur.execute('SELECT DISTINCT bank FROM questions')
        banks = [r['bank'] for r in cur.fetchall()]
        tot = 0
        for b in banks:
            g = bankgrp(b)
            cur.execute('UPDATE questions SET bankgrp=%s WHERE bank=%s', (g, b))
            tot += cur.rowcount
            print(f'  {g:10s} {b}')
        con.commit()
        print('bankgrp updated:', tot, 'rows,', len(banks), 'banks')

if __name__ == '__main__':
    main()
