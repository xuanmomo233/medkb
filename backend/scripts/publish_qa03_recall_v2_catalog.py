"""Publish mounted catalog data with rollback, without growing application images."""
import base64
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / "docs/audit-evidence"
BASELINE = E / "question-recall-v2-deployment-baseline-20261019.json"
CATALOG = E / "question-review-catalog-recall-v2-publication-20261019.json"
RECEIPT = E / "question-recall-v2-deployment-receipt-20261019.json"

REMOTE = r'''import base64,fcntl,gzip,hashlib,json,os,subprocess,tempfile,time,urllib.request,zlib
from pathlib import Path
baseline=BASELINE_DATA
raw=zlib.decompress(base64.b64decode(CATALOG_B64))
expected=CATALOG_SHA
assert hashlib.sha256(raw).hexdigest()==expected
report={'catalog_sha256':expected,'question_data_write_performed':False,'review_decision_write_performed':False}
def run(args):
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
 if r.returncode:raise RuntimeError(str(args[:3])+': '+r.stderr.decode('utf-8','replace')[-2000:])
 return r.stdout
def inspect():return json.loads(run(['docker','inspect','medkb-api']))[0]
def catalog():return run(['docker','exec','medkb-api','cat','/srv/app/data/question_evidence_review_queue.json'])
def health():
 for _ in range(30):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8899/api/health',timeout=3) as r:
    if r.status==200:return True
  except Exception:pass
  time.sleep(.5)
 return False
lock=open('/opt/medkb-v2/.qa-recall-publication.lock','a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
current=inspect()
if current['Image']!=baseline['image_id'] or hashlib.sha256(catalog()).hexdigest()!=baseline['catalog_sha256']:
 raise ValueError('production image/catalog changed since baseline; refusing to overwrite')
source=Path('/opt/medkb-v2/src/backend/app/data/question_evidence_review_queue.json')
mounted=[m for m in current.get('Mounts',[]) if m.get('Destination')=='/srv/app/data/question_evidence_review_queue.json']
if len(mounted)!=1 or mounted[0].get('Type')!='bind' or mounted[0].get('Source')!=str(source) or mounted[0].get('RW') is not False:
 raise ValueError('read-only catalog bind mount required; do not build another catalog image layer')
source_before=source.read_bytes()
if hashlib.sha256(source_before).hexdigest()!=baseline['catalog_sha256']:
 raise ValueError('host catalog differs from running baseline')
def atomic_catalog(data):
 with tempfile.NamedTemporaryFile(dir=source.parent,prefix='.catalog-',delete=False) as f:
  temp=Path(f.name)
  try:
   f.write(data);f.flush();os.fsync(f.fileno());os.chmod(temp,0o644)
  except BaseException:
   temp.unlink(missing_ok=True);raise
 try:os.replace(temp,source)
 finally:temp.unlink(missing_ok=True)
old_catalog=json.loads(catalog());new_catalog=json.loads(raw);by_id={i['id']:i for i in new_catalog['items']}
if old_catalog['dataset_id']!=new_catalog['dataset_id'] or not all(by_id.get(i['id'])==i for i in old_catalog['items']):
 raise ValueError('existing catalog items or dataset changed')
release=Path(RELEASE_PATH);release.mkdir(exist_ok=False)
with gzip.open(release/'question_evidence_review_queue.before.json.gz','wb') as f:f.write(source_before)
(release/'baseline.json').write_text(json.dumps(baseline,indent=2))
if inspect()['Image']!=baseline['image_id'] or hashlib.sha256(catalog()).hexdigest()!=baseline['catalog_sha256']:
 raise ValueError('production changed before catalog replacement')
compose=['docker','compose','--project-directory','/opt/medkb-v2/src/deploy','-p','deploy','-f','/opt/medkb-v2/src/deploy/docker-compose.yml','up','-d','--no-build','--force-recreate','api']
try:
 atomic_catalog(raw)
 run(compose)
 if not health():raise RuntimeError('health check failed')
 if hashlib.sha256(catalog()).hexdigest()!=expected:raise RuntimeError('running catalog hash differs')
 if inspect()['Image']!=baseline['image_id']:raise RuntimeError('catalog-only publication unexpectedly changed application image')
 report.update({'deployed':True,'rolled_back':False,'publication_mode':'mounted-catalog','image_before':baseline['image_id'],'image_after':inspect()['Image'],'health_passed':True,'legacy_items_preserved':len(old_catalog['items']),'total_question_review_items':len(new_catalog['items']),'recall':new_catalog['recall'],'server_release_directory':str(release)})
except Exception as e:
 atomic_catalog(source_before)
 run(compose)
 report.update({'deployed':False,'rolled_back':True,'rollback_health_passed':health(),'error':str(e)})
(release/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--release-dir", default="/opt/medkb-v2/qa-recall-v2-20261019")
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError(args.receipt)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    raw = args.catalog.read_bytes()
    remote = REMOTE.replace("BASELINE_DATA", repr(baseline)).replace("CATALOG_B64", repr(base64.b64encode(zlib.compress(raw)).decode())).replace("CATALOG_SHA", repr(hashlib.sha256(raw).hexdigest())).replace("RELEASE_PATH", repr(args.release_dir))
    result = subprocess.run(["ssh.exe", "-i", r"D:\Desktop\axs.pem", "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=12", "axs-vps", "python3", "-"], input=remote.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    report = json.loads(result.stdout.decode("utf-8"))
    args.receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("deployed") is not True:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
