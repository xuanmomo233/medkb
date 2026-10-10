# -*- coding: utf-8 -*-
"""把知识库三类内容解析进 SQLite（kb.db）：
- questions : 题库/*.md 逐题（含共用题干子题）
- kp_items  : 知识点/*/*.md 的条目（- **术语**：内容）+ 体征速查
- chapters  : 导图章节 md + 知识点分册全文（浏览用）
- docs+fts  : 统一搜索索引（FTS5 trigram，支持中文子串）
- progress  : 背诵/刷题进度（SM-2 简化）
"""
import json, os, re, glob, sqlite3

KB = r'D:\Desktop\医学知识库'
SRC = r'D:\IDEA\project\.devin-tmp\wcyk_questions'
DB = r'D:\IDEA\project\.devin-tmp\study_app\kb.db'

# 系统关键词（章节级）
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
        if re.search(pat, text):
            return s
    return '其他'

QTYPE = {'1': '单选', '2': '多选', '3': '多选', '5': '口诀', '6': '病例串', '7': '填空'}

def build_qmeta():
    """qid -> (qtype, system)；共用题干子题也纳入"""
    qm = {}
    for bdir in sorted(os.listdir(SRC)):
        bp = os.path.join(SRC, bdir)
        if not os.path.isdir(bp):
            continue
        for f in glob.glob(os.path.join(bp, '*.json')):
            if f.endswith('_chapters.json'):
                continue
            d = json.load(open(f, encoding='utf-8'))
            ch_sys = sys_of(d['chapter']['title'])
            for q in d['questions']:
                t = str(q.get('type'))
                qm[str(q['id'])] = (QTYPE.get(t, '其他'), ch_sys)
                if t == '6':
                    for sq in (q.get('subQuestion') or []):
                        qm[str(sq['id'])] = ('病例子题', ch_sys)
    return qm

def parse_qmd(fp):
    txt = open(fp, encoding='utf-8').read()
    head_m = re.search(r'章节ID:(\d+) \| 题库ID:(\d+) \| 共(\d+)题', txt)
    title_m = re.match(r'# (.+)', txt)
    meta = {'cid': head_m.group(1) if head_m else '', 'bid': head_m.group(2) if head_m else '',
            'declared': int(head_m.group(3)) if head_m else 0,
            'chapter_title': title_m.group(1).strip() if title_m else os.path.basename(fp)}
    parts = re.split(r'\n(?=### 第\d+题 )', txt)
    qs = []
    for p in parts[1:]:
        m = re.match(r'### 第(\d+)题 `id:([^`]+)`(?:\s*\|\s*(.*))?', p)
        if not m:
            continue
        idx, qid, mline = int(m.group(1)), m.group(2), m.group(3) or ''
        body = p[m.end():]
        parent = ''
        pm = re.search(r'>\s*共用题干[:：](.*?)\n\n', body, re.S)
        if pm:
            parent = pm.group(1).strip()
            body = body[pm.end():]
        am = re.search(r'\*\*答案[:：](.*?)\*\*', body)
        ans = am.group(1).strip() if am else ''
        anm = re.search(r'\*\*解析\*\*[:：](.*?)(?=\n---|\Z)', body, re.S) or \
              re.search(r'\*\*解析[:：]\*\*(.*?)(?=\n---|\Z)', body, re.S)
        analysis = anm.group(1).strip() if anm else ''
        stem_area = body[:am.start()] if am else body
        stem_area = re.split(r'\*\*解析', stem_area)[0].strip()
        opts = re.findall(r'^- ([A-Z])\. (.*)$', stem_area, re.M)
        stem = re.split(r'^- [A-Z]\. ', stem_area, flags=re.M)[0].strip()
        qs.append({'qid': qid, 'idx': idx, 'stem': stem, 'options': [o[1] for o in opts],
                   'answer': ans, 'analysis': analysis, 'parent_stem': parent, 'meta': mline})
    return meta, qs

def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript('''
    CREATE TABLE questions(id INTEGER PRIMARY KEY, qid TEXT, bank TEXT, subjdir TEXT,
        chapter TEXT, stem TEXT, options TEXT, answer TEXT, analysis TEXT,
        parent TEXT, meta TEXT, srcfile TEXT, qtype TEXT, system TEXT);
    CREATE TABLE kp_items(id INTEGER PRIMARY KEY, subj TEXT, subj_real TEXT, part TEXT,
        section TEXT, term TEXT, hint TEXT, body TEXT, qids TEXT, srcfile TEXT);
    CREATE TABLE chapters(id INTEGER PRIMARY KEY, subj TEXT, title TEXT,
        content TEXT, srcfile TEXT, kind TEXT);
    CREATE TABLE progress(kind TEXT, ref TEXT, reps INTEGER DEFAULT 0, ease REAL DEFAULT 2.5,
        interval_d REAL DEFAULT 0, due REAL DEFAULT 0, state TEXT DEFAULT '',
        starred INTEGER DEFAULT 0, last_ts REAL DEFAULT 0, PRIMARY KEY(kind, ref));
    CREATE TABLE docs(id INTEGER PRIMARY KEY, kind TEXT, ref_id INTEGER, title TEXT);
    CREATE VIRTUAL TABLE fts USING fts5(text, tokenize='trigram');
    ''')

    def add_doc(kind, ref_id, title, text):
        cur = con.execute('INSERT INTO docs(kind,ref_id,title) VALUES(?,?,?)', (kind, ref_id, title))
        con.execute('INSERT INTO fts(rowid, text) VALUES(?,?)', (cur.lastrowid, text))

    # ---- 题库 ----
    qmeta = build_qmeta()
    nq = 0
    for sd in sorted(os.listdir(os.path.join(KB, '题库'))):
        dp = os.path.join(KB, '题库', sd)
        if not os.path.isdir(dp) or sd.startswith('00-'):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith('.md') or fn.startswith('INDEX'):
                continue
            fp = os.path.join(dp, fn)
            meta, qs = parse_qmd(fp)
            for q in qs:
                qt, qsys = qmeta.get(q['qid'], ('其他', ''))
                if not qsys or qsys == '其他':
                    qsys = sys_of(q['stem'] + ' ' + q['analysis'] + ' ' + ' '.join(q['options']))
                cur = con.execute(
                    'INSERT INTO questions(qid,bank,subjdir,chapter,stem,options,answer,analysis,parent,meta,srcfile,qtype,system) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (q['qid'], meta['chapter_title'].split('·')[0].strip(), sd,
                     meta['chapter_title'], q['stem'], json.dumps(q['options'], ensure_ascii=False),
                     q['answer'], q['analysis'], q['parent_stem'], q['meta'],
                     os.path.relpath(fp, KB), qt, qsys))
                nq += 1
                add_doc('q', cur.lastrowid, meta['chapter_title'] + f' 第{q["idx"]}题',
                        q['stem'] + ' ' + ' '.join(q['options']) + ' ' + q['analysis'] + ' ' + q['parent_stem'])
    print('questions:', nq)

    # ---- 知识点条目 ----
    nkp = 0
    kp_root = os.path.join(KB, '知识点')

    def real_subj(subj_dir, sec):
        """_真题模考补充 的条目按 ## 小节名归回真实学科"""
        if subj_dir != '_真题模考补充':
            return subj_dir
        m = [('生理', '生理学'), ('生物化学', '生物化学'), ('生化', '生物化学'), ('分子生物', '生物化学'),
             ('病理', '病理学'), ('诊断', '诊断学'), ('体征', '诊断学'), ('症状', '诊断学'),
             ('外科', '外科学'), ('骨科', '外科学'), ('普外', '外科学'), ('泌尿外', '外科学'),
             ('烧伤', '外科学'), ('麻醉', '外科学'), ('内科', '内科学'), ('呼吸', '内科学'),
             ('循环', '内科学'), ('心血管', '内科学'), ('消化', '内科学'), ('泌尿', '内科学'),
             ('血液', '内科学'), ('内分泌', '内科学'), ('风湿', '内科学'), ('中毒', '内科学'),
             ('肾脏', '内科学'), ('心内膜炎', '内科学'), ('人文', '医学人文'), ('法规', '医学人文'),
             ('伦理', '医学人文'), ('性传播', '内科学'), ('性病', '内科学')]
        for kw, s in m:
            if kw in sec:
                return s
        return '综合'

    for subj_dir in sorted(os.listdir(kp_root)):
        dp = os.path.join(kp_root, subj_dir)
        if not os.path.isdir(dp) or subj_dir.startswith('_'):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith('.md') or fn == 'INDEX.md':
                continue
            fp = os.path.join(dp, fn)
            txt = open(fp, encoding='utf-8').read()
            cur = con.execute('INSERT INTO chapters(subj,title,content,srcfile,kind) VALUES(?,?,?,?,?)',
                              ('知识点·' + subj_dir, fn[:-3], txt, os.path.relpath(fp, KB), 'kp'))
            add_doc('c', cur.lastrowid, f'知识点 {subj_dir} {fn[:-3]}', txt[:20000])
            sec = ''
            for line in txt.split('\n'):
                hm = re.match(r'##\s+(.+)', line)
                if hm:
                    sec = hm.group(1).strip()
                    continue
                ls = line.strip()
                if not ls.startswith('- ') or len(ls) <= 8:
                    continue
                content = ls[2:]
                cm = re.match(r'(.{2,60}?)[：:]\s*(.+)', content, re.S)
                if cm:
                    term = re.sub(r'\*+', '', cm.group(1)).strip()
                    body = cm.group(2).strip()
                else:
                    body = content
                    term = re.sub(r'\*+', '', re.split(r'[，,；;。]', content)[0][:18]).strip()
                qids = ' '.join(re.findall(r'\[Q[^\]]+\]', body))
                body = re.sub(r'\s*\[Q[^\]]+\]', '', body).strip()
                if 0 < len(term) <= 60 and len(body) >= 4:
                    cur = con.execute('INSERT INTO kp_items(subj,subj_real,part,section,term,hint,body,qids,srcfile) VALUES(?,?,?,?,?,?,?,?,?)',
                                      (subj_dir, subj_dir, fn[:-3], sec, term, '', body, qids, os.path.relpath(fp, KB)))
                    nkp += 1
                    add_doc('k', cur.lastrowid, f'{subj_dir}·{fn[:-3]}·{sec}', term + ' ' + body)
    print('kp_items:', nkp)

    # ---- 体征速查 → kp_items ----
    sf = os.path.join(kp_root, '体征-疾病速查.md')
    if os.path.exists(sf):
        txt = open(sf, encoding='utf-8').read()
        for m in re.finditer(r'##\s+(.+?)\n(.*?)(?=\n##\s|\Z)', txt, re.S):
            sign, body = re.sub(r'\*+', '', m.group(1)).strip(), m.group(2)
            items = [re.sub(r'^-\s*', '', l).strip() for l in body.split('\n') if l.strip().startswith('-')]
            if items:
                body_txt = '\n'.join('- ' + i for i in items)
                cur = con.execute('INSERT INTO kp_items(subj,subj_real,part,section,term,hint,body,qids,srcfile) VALUES(?,?,?,?,?,?,?,?,?)',
                                  ('体征速查', '体征速查', '体征-疾病速查', '速查', sign, '', body_txt, '', '知识点/体征-疾病速查.md'))
                nkp += 1
                add_doc('k', cur.lastrowid, f'体征 {sign}', sign + ' ' + body_txt)

    # ---- 导图章节 ----
    nch = 0
    for subj in ['生理学', '生物化学', '病理学', '内科学', '外科学']:
        dp = os.path.join(KB, subj)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if fn.endswith('.md'):
                fp = os.path.join(dp, fn)
                txt = open(fp, encoding='utf-8').read()
                cur = con.execute('INSERT INTO chapters(subj,title,content,srcfile,kind) VALUES(?,?,?,?,?)',
                                  (subj, fn[:-3], txt, os.path.relpath(fp, KB), 'mm'))
                nch += 1
                add_doc('c', cur.lastrowid, f'{subj}·{fn[:-3]}', txt[:20000])
    print('chapters:', nch)

    con.execute('CREATE INDEX idx_q_subj ON questions(subjdir)')
    con.execute('CREATE INDEX idx_q_ch ON questions(chapter)')
    con.execute('CREATE INDEX idx_q_sys ON questions(system)')
    con.execute('CREATE INDEX idx_q_type ON questions(qtype)')
    con.execute('CREATE INDEX idx_q_bank ON questions(bank)')
    con.execute('CREATE INDEX idx_kp_subj ON kp_items(subj)')
    con.execute('CREATE INDEX idx_docs ON docs(kind, ref_id)')
    con.commit()
    con.close()
    print('DB done:', os.path.getsize(DB) // (1 << 20), 'MB')

if __name__ == '__main__':
    main()
