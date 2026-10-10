import psycopg2, psycopg2.extras
con = psycopg2.connect('dbname=medkb user=user_DeDhkF password=password_6XeeG8 host=127.0.0.1',
                       cursor_factory=psycopg2.extras.RealDictCursor)
cur = con.cursor()
cur.execute("SELECT COUNT(*) c FROM questions WHERE qid::bigint > 235287")
print('new rows:', cur.fetchone()['c'])
cur.execute("SELECT bank, COUNT(*) c FROM questions WHERE qid::bigint > 235287 GROUP BY bank ORDER BY c DESC")
for r in cur.fetchall():
    print(' ', r['bank'], r['c'])
cur.execute("SELECT qid, chapter, stem, answer, qtype, system FROM questions WHERE qid='235290'")
r = cur.fetchone()
for k, v in r.items():
    print(k, ':', str(v)[:200])
cur.execute("SELECT COUNT(*) c, COUNT(NULLIF(analysis,'')) a FROM questions WHERE qid::bigint > 235287")
r = cur.fetchone()
print('with analysis:', r['a'], '/', r['c'])
