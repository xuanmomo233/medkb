# -*- coding: utf-8 -*-
"""万川题库增量同步：
扫描 id>watermark 的新题目 → 转成行 → INSERT 进 PG + 存档原始 JSON。
用法: python3 wcyk_sync.py [--batch 500] [--dry]
"""
import json, os, re, sys, time, html as ihtml
import urllib.request, urllib.parse
import psycopg2, psycopg2.extras
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wcyk_api import api

WORK = '/opt/medkb'
STATE = os.path.join(WORK, 'sync_state.json')
ARCHIVE = os.path.join(WORK, 'wcyk_questions')
DB = 'dbname=medkb user=user_DeDhkF password=password_6XeeG8 host=127.0.0.1'

QTYPE = {'1': '单选', '2': '多选', '3': '多选', '5': '口诀', '6': '病例串', '7': '填空'}
LETTERS = 'ABCDEFGHIJ'

# 系统关键词（同 build_db）
SYS_KW = [
 ('呼吸系统', '呼吸|肺|COPD|哮喘|支扩|肺炎|结核|胸膜|气胸|呼衰|ARDS|肺栓|间质|肺心病|肺癌|肺脓肿|胸腔积液|呼吸衰竭|咯血|发绀'),
 ('循环系统', '循环|心血管|心衰|心力衰竭|心律|高血压|冠心|心绞痛|心肌梗|心梗|瓣膜|心肌病|心肌炎|心包|心内膜炎|心脏骤停|猝死|动脉粥样硬化|雷诺|脉管炎|深静脉|静脉曲张|动脉瘤|心脏|心音|杂音|心界|奇脉|水冲脉|奔马律|开瓣音|起搏|电复律|洋地黄|BNP|NYHA'),
 ('消化系统', '消化|胃|肠|食管|GERD|反流|溃疡|肠结核|腹膜|肝硬化|肝性脑|肝癌|胆|胰|阑尾|疝|肛管|痔|结直肠|克罗恩|黄疸|腹水|消化道出血|胃肠|胰腺|胆囊|胆道|门脉|门静脉|肠梗阻|便血|呕血|腹痛|腹泻|便秘|幽门|胃镜|肠镜|结肠'),
 ('泌尿系统', '泌尿|肾|肾小球|肾炎|肾病|尿路|肾衰|肾小管|透析|IgA|肾病综合征|蛋白尿|血尿|肌酐|尿素氮|GFR|前列腺增生|膀胱|尿石|肾结石|输尿管|尿道|肾癌|肾盂|肾积水|尿潴留|尿失禁'),
 ('血液系统', '血液|贫血|白血病|淋巴瘤|骨髓瘤|出血性疾病|血小板|凝血|输血|再障|溶血|MDS|缺铁|巨幼|紫癜|DIC|血友|ITP|骨髓增生|全血细胞|血红蛋白|网织红|骨髓|脾大'),
 ('内分泌与代谢', '内分泌|代谢|糖尿|DKA|酮症|甲亢|甲减|Graves|桥本|甲状腺|库欣|皮质醇|原醛|醛固酮|嗜铬|垂体|催乳素|生长激素|肢端|痛风|尿酸|骨质|肥胖|代谢综合征|胰岛素|低血糖|TSH|甲状旁腺|钙磷|高脂血'),
 ('神经精神', '神经|精神|脑|癫痫|帕金森|重症肌无力|脊髓|格林巴利|吉兰|偏头痛|颅内|脑血管|中枢|脱髓鞘|痴呆|阿尔茨|谵妄|精神分裂|抑郁|焦虑|神经症|癔症|心理障碍|突触|反射|感觉|递质|自主神经|交感|副交感'),
 ('风湿免疫', '风湿|类风湿|狼疮|SLE|干燥|强直|血管炎|皮肌炎|系统性硬化|贝赫切特|白塞|ANCA|抗核抗体|类风湿因子|抗CCP|骨关节炎|痛风性'),
 ('骨科运动', '骨折|脱位|关节|脊柱|椎间盘|颈椎病|腰椎|骨髓炎|骨结核|骨肿瘤|手外伤|周围神经|运动系统|腱鞘|韧带|半月板|骨盆|股骨|胫骨|肱骨|桡骨|尺骨|髌骨|锁骨|踝|肩|肘|髋|腕管|肘管|截肢|牵引|石膏|筋膜室|骨痂|骨不连'),
 ('生殖乳腺', '生殖|乳腺|乳房|宫颈|子宫|卵巢|睾丸|妊娠|产科|妇科|孕|分娩|流产|宫外孕|葡萄胎|绒癌|月经|排卵|前列腺|精索|鞘膜|隐睾|阴茎|性功能'),
 ('感染传染', '感染|传染|梅毒|艾滋|AIDS|HIV|淋病|尖锐湿疣|伤寒|痢疾|阿米巴|血吸虫|疟疾|钩端|鼠疫|霍乱|出血热|狂犬病|流脑|乙脑|麻疹|风疹|水痘|腮腺|手足口|寄生虫|真菌|念珠|曲霉|隐球菌|败血症|脓毒|脓毒症|破伤风|气性坏疽|蜂窝|丹毒'),
 ('外科总论', '无菌|消毒|灭菌|麻醉|围术期|术前|术后|外科营养|创伤|烧伤|战伤|咬伤|冻伤|清创|换药|拆线|引流|伤口|微创|腹腔镜|介入|外科休克|复苏|水电解质|酸碱|体液|脱水|低钾|高钾|低钠|补液|肠内营养|肠外营养|切口|无菌术|手术室'),
 ('基础医学', '生理|生化|生物化学|病理|药理|蛋白质|核酸|酶|维生素|糖代谢|脂代谢|氨基酸|核苷酸|生物氧化|基因|分子生物|信号转导|DNA|RNA|癌基因|血红素|胆汁酸|胆色素|肝生化|血液生化|适应|损伤|修复|炎症|免疫病理|局部血液|梗死|坏死|凋亡|化生|跨膜|电位|心动周期|气体运输|凝血|血型|肾小球滤过|肾小管'),
 ('诊断学基础', '诊断|检体|体征|心电图|实验室|影像|超声|内镜|穿刺|活检|化验|检查|症状|问诊|病史|体格检查|视诊|触诊|叩诊|听诊'),
 ('人文法规', '人文|伦理|医患|法规|执业|卫生法|医德|心理|知情同意|医疗事故|处方|器官移植|献血|传染病防治|医师法|医疗纠纷|临终|脑死亡|侵权责任'),
]
def sys_of(text):
    for s, pat in SYS_KW:
        if re.search(pat, text or ''):
            return s
    return '其他'

def h2t(h):
    """HTML → 文本：img→![图](src)，br/p→换行，去其余标签，反转义"""
    if not h:
        return ''
    h = re.sub(r'<img[^>]*?src=["\']([^"\']+)["\'][^>]*>', r'![图](\1)', h)
    h = re.sub(r'<br\s*/?>', '\n', h)
    h = re.sub(r'</p\s*>', '\n', h)
    h = re.sub(r'<[^>]+>', '', h)
    h = ihtml.unescape(h)
    return re.sub(r'\n{3,}', '\n\n', h).strip()

EXCLUDE_BANK = re.compile(r'政治|肖秀荣|肖\d|腿四|徐涛|毛中特|马原|思修|英语|田静|作文|阅读')

def excluded_bank(title):
    return bool(EXCLUDE_BANK.search(title or ''))

def bank_subjdir(title):
    """bank 名→学科目录：新题库优先按关键词归类到现有目录，否则 12-新增"""
    t = title or ''
    if re.search(r'口诀', t): return '00-口诀速记'
    if re.search(r'真题|历年|十年', t): return '08-真题套卷'
    if re.search(r'模考|押题|模拟|预测|阶段测|摸底|每日|小测|巩固', t): return '09-模拟押题'
    if re.search(r'人文|伦理|法规|医德', t): return '07-医学人文'
    if re.search(r'生理', t): return '01-生理学'
    if re.search(r'生化|分子|基因', t): return '02-生物化学'
    if re.search(r'病理', t): return '03-病理学'
    if re.search(r'诊断|检体', t): return '04-诊断学'
    if re.search(r'内科', t): return '05-内科学'
    if re.search(r'外科', t): return '06-外科学'
    return '12-新增题库'

def bankgrp(title):
    """题库系分类：天门(ttsx/师兄)·亮门(xl)·老贺(HYC)·年份"""
    t = title or ''
    if re.search(r'ttsx|天门|天天|师兄', t, re.I):
        series = '天门'
    elif re.search(r'亮门|小亮|(?<![a-z])xl(?![a-z])', t, re.I):
        series = '亮门'
    elif re.search(r'老贺|HYC|贺银成', t, re.I):
        series = '老贺'
    elif re.search(r'YKB|医考帮', t, re.I):
        series = '医考帮'
    else:
        series = '综合'
    y = re.match(r'【?(\d{2})[版年届]?', t)
    if not y:
        y = re.search(r'(?<!\d)(2[0-9])(?=届|版|年|级)', t)
    yr = (y.group(1) + '届') if y else ('历年' if re.search(r'历年|真题|十年', t) else '')
    return series + ('·' + yr if yr else '')

# ---------- 缓存层 ----------
_banks = {}
_chapters = {}

def bank_info(bid):
    if not _banks:
        j = api('/api/q_bank', {'pageSize': 500}, auth=False)
        data = j.get('data')
        rows = data.get('data', data) if isinstance(data, dict) else data
        for b in (rows or []):
            _banks[b['id']] = b
    return _banks.get(bid) or {}

def chapter_info(bid, cid):
    if bid not in _chapters:
        try:
            j = api('/api/chapter', {'qBankId': bid}, auth=False)
            m = {}
            for c in j.get('data', []):
                m[c['id']] = c
                for k in (c.get('children') or []):
                    m[k['id']] = k
            _chapters[bid] = m
        except Exception:
            _chapters[bid] = {}
    return _chapters[bid].get(cid) or {}

def chapter_title(bid, cid):
    c = chapter_info(bid, cid)
    t = c.get('title', '')
    if c.get('parentId'):
        p = chapter_info(bid, c['parentId'])
        if p.get('title'):
            t = p['title'] + ' / ' + t
    return t or str(cid)

# ---------- 行转换 ----------
def q_to_row(q, existing_qids):
    """api question dict → questions 行 dict；已有 qid 返回 None"""
    qid = str(q['id'])
    if qid in existing_qids:
        return None
    bid = q.get('qBankId'); cid = q.get('chapterId')
    b = bank_info(bid)
    bank_title = b.get('title', '')
    if excluded_bank(bank_title):
        return 'skip'
    typ = str(q.get('type'))
    opts = [h2t(o) for o in (q.get('options') or [])]
    ans = q.get('answer') or []
    letters = []
    if isinstance(ans, list):
        for a in ans:
            if isinstance(a, int):
                letters.append(LETTERS[a] if a < len(LETTERS) else str(a))
            elif isinstance(a, str) and not a.strip().startswith('<'):
                letters.append(a.strip())
    answer = '、'.join(letters) if letters else h2t(' '.join(str(x) for x in ans))
    stud = q.get('studCount') or 0
    right = q.get('rightCount') or 0
    rate = round(100 * right / stud) if stud else 0
    meta = f"做过{stud} · 正确率{rate}% · 难度{q.get('difficulty', 1)}"
    pid = q.get('parentId') or 0
    parent = ''
    if pid:
        try:
            pj = api('/api/question', {'id': pid})
            pq = pj.get('data') or {}
            parent = h2t(pq.get('stem'))
        except Exception:
            pass
    ct = chapter_title(bid, cid)
    return {
        'qid': qid, 'bank': bank_title, 'subjdir': bank_subjdir(bank_title),
        'bankgrp': bankgrp(bank_title),
        'chapter': f"{bank_title} · {ct}" if bank_title else ct,
        'stem': h2t(q.get('stem')), 'options': json.dumps(opts, ensure_ascii=False),
        'answer': answer, 'analysis': h2t(q.get('analysis')), 'parent': parent,
        'meta': meta,
        'srcfile': f"题库\\{bank_subjdir(bank_title)}\\{bank_title}__{ct.replace('/', '_')}.md",
        'qtype': QTYPE.get(typ, '单选'),
        'system': sys_of((q.get('stem') or '') + ' ' + (q.get('analysis') or '') + ' '.join(opts)),
    }

# ---------- 主流程 ----------
def main():
    batch = 500
    dry = '--dry' in sys.argv
    for i, a in enumerate(sys.argv):
        if a == '--batch' and i + 1 < len(sys.argv):
            batch = int(sys.argv[i + 1])
    st = {}
    if os.path.exists(STATE):
        st = json.load(open(STATE))
    con = psycopg2.connect(DB, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = con.cursor()
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS questions_qid_uidx ON questions(qid)')
    cur.execute('ALTER TABLE questions ADD COLUMN IF NOT EXISTS bankgrp text')
    con.commit()
    cur.execute('SELECT qid FROM questions')
    existing = {r['qid'] for r in cur.fetchall()}
    cur.execute('SELECT MAX(qid::bigint) m FROM questions')
    db_max = int(cur.fetchone()['m'] or 0)
    start = max(st.get('last_qid', 0), db_max)
    print(f'start_qid={start} existing={len(existing)} dry={dry}', flush=True)

    new_rows, misses, scanned = [], 0, 0
    qid = start
    while scanned < batch and misses < 60:
        qid += 1
        scanned += 1
        try:
            j = api('/api/question', {'id': qid})
        except Exception as e:
            print('err', qid, e, flush=True); time.sleep(1); continue
        q = j.get('data')
        if j.get('errno') != 0 or not q:
            misses += 1
        else:
            misses = 0
            for qi in (q if isinstance(q, list) else [q]):
                r = q_to_row(qi, existing)
                if r == 'skip':
                    continue
                if r:
                    new_rows.append((qi, r))
                    if len(new_rows) % 25 == 0:
                        print(f'... +{len(new_rows)} (qid {qid})', flush=True)
        time.sleep(0.08)
    print(f'scanned={scanned} new={len(new_rows)} frontier={qid}', flush=True)

    if dry or not new_rows:
        for q, r in new_rows[:5]:
            print(r['qid'], '|', r['bank'], '|', r['chapter'], '|', r['stem'][:60])
        return

    # 入库
    cur.execute('SELECT MAX(id) m FROM questions')
    nid = int(cur.fetchone()['m'] or 0)
    rows = []
    for _, r in new_rows:
        nid += 1
        r['id'] = nid
        rows.append(r)
    cur.executemany(
        'INSERT INTO questions(id,qid,bank,bankgrp,subjdir,chapter,stem,options,answer,analysis,parent,meta,srcfile,qtype,system) '
        'VALUES(%(id)s,%(qid)s,%(bank)s,%(bankgrp)s,%(subjdir)s,%(chapter)s,%(stem)s,%(options)s,%(answer)s,%(analysis)s,%(parent)s,%(meta)s,%(srcfile)s,%(qtype)s,%(system)s) '
        'ON CONFLICT (qid) DO NOTHING',
        rows)
    con.commit()
    print(f'inserted {len(new_rows)}', flush=True)

    # 原始 JSON 按章节归档（与原 wcyk_questions 同构）
    by_ch = {}
    for q, r in new_rows:
        by_ch.setdefault((q.get('qBankId'), q.get('chapterId')), []).append(q)
    for (bid, cid), qs in by_ch.items():
        b = bank_info(bid)
        dname = f"{bid}_{b.get('title','').replace('/', '_')}"
        dp = os.path.join(ARCHIVE, dname)
        os.makedirs(dp, exist_ok=True)
        fp = os.path.join(dp, f'{cid}.json')
        old = {'chapter': chapter_info(bid, cid), 'questions': []}
        if os.path.exists(fp):
            try:
                old = json.load(open(fp, encoding='utf-8'))
            except Exception:
                pass
        old_ids = {str(x['id']) for x in old.get('questions', [])}
        old['questions'] += [x for x in qs if str(x['id']) not in old_ids]
        json.dump(old, open(fp, 'w', encoding='utf-8'), ensure_ascii=False)
    st['last_qid'] = qid
    json.dump(st, open(STATE, 'w'))
    print(f'archived chapters: {len(by_ch)} | state last_qid={qid}', flush=True)

if __name__ == '__main__':
    main()
