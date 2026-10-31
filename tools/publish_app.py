"""Publish a verified release receipt to the mounted APK endpoint with rollback."""
import argparse,base64,hashlib,json,subprocess
from pathlib import Path

HOST=r'''
import fcntl,hashlib,json,os,re,shutil,subprocess,time,datetime
from pathlib import Path
release=RELEASE
stage=Path(STAGE)
apk=Path('/opt/medkb/app-release.apk');env=Path('/opt/medkb-v2/src/deploy/.env')
compose=['docker','compose','--project-directory','/opt/medkb-v2/src/deploy']
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=150)
 if p.returncode:raise RuntimeError(p.stdout[-2000:]+p.stderr[-2000:])
 return p.stdout.strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def version():return json.loads(run(['curl','-fsS','http://127.0.0.1:8899/api/version']))
def wait(build,digest):
 for i in range(20):
  try:
   v=version()
   if v['build']==build and v['apk_sha256']==digest:
    for u in ['http://127.0.0.1:8899/api/health','https://luck.021209.xyz/api/health']:assert json.loads(run(['curl','-fsS',u]))['status']=='ok'
    return v
  except Exception:pass
  time.sleep(2)
 raise RuntimeError('version/health postread failed')
with open('/opt/medkb-v2/.qa-recall-publication.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 old=version()
 if old['build']>=release['build']:raise RuntimeError('live version is not older; inspect before retry')
 if old['apk_sha256']!=release['previous_apk_sha256'] or sha(apk)!=old['apk_sha256']:raise RuntimeError('installed APK drift')
 if sha(stage)!=release['sha256']:raise RuntimeError('uploaded APK SHA mismatch')
 if not release.get('signer_matches') or not release.get('v1_v2_verified'):raise RuntimeError('release signing gates not passed')
 info=json.loads(run(['docker','inspect','medkb-api']))[0]
 env_raw=env.read_bytes();env_text=env_raw.decode('utf-8-sig')
 if len(re.findall(r'^MEDKB_VERSION=.*$',env_text,re.M))!=1:raise RuntimeError('ambiguous MEDKB_VERSION')
 backup=Path('/opt/medkb-v2/ops-backups/app-build'+str(release['build'])+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
 backup.mkdir();os.chmod(backup,0o700)
 (backup/'deploy.env').write_bytes(env_raw);os.chmod(backup/'deploy.env',0o600)
 os.link(apk,backup/'previous.apk')
 result={'build':release['build'],'backup':str(backup),'old_build':old['build'],'api_image_before':info['Image']}
 try:
  os.replace(stage,apk)
  new_line="MEDKB_VERSION='"+str(release['build'])+'|v'+release['version']+" 教材页图独立索引与阅读修复'"
  updated=re.sub(r'^MEDKB_VERSION=.*$',lambda _:new_line,env_text,flags=re.M)
  tmp=env.with_name('.env.app-release.tmp');tmp.write_bytes(updated.encode('utf-8'));os.chmod(tmp,0o600);os.replace(tmp,env)
  run(compose+['up','-d','--no-build','--force-recreate','api'])
  result['version']=wait(release['build'],release['sha256'])
  current=json.loads(run(['docker','inspect','medkb-api']))[0]
  assert current['Image']==info['Image'],'app publishing changed the API image'
  assert sorted((x['Source'],x['Destination'],x['RW']) for x in current['Mounts'])==sorted((x['Source'],x['Destination'],x['RW']) for x in info['Mounts'])
  result.update({'published':True,'sha256':sha(apk),'api_image_unchanged':True,'mounts_unchanged':True})
 except Exception as exc:
  result.update({'published':False,'error':str(exc)})
  restored=apk.with_name('app-release.rollback.tmp');shutil.copyfile(backup/'previous.apk',restored);os.replace(restored,apk)
  env.write_bytes(env_raw);run(compose+['up','-d','--no-build','--force-recreate','api']);result['rollback_version']=wait(old['build'],old['apk_sha256'])
  (backup/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));raise SystemExit(1)
 (backup/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('publication receipt already exists')
 r=json.loads(a.receipt.read_text(encoding='utf-8'));apk=Path(r['apk']).resolve()
 if hashlib.sha256(apk.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('local APK changed')
 stage='/opt/medkb-v2/ops-backups/staged-app-build'+str(r['build'])+'-'+r['sha256'][:16]+'.apk'
 scp=['C:/Windows/System32/OpenSSH/scp.exe','-i','D:/Desktop/axs.pem','-o','BatchMode=yes','-o','IdentitiesOnly=yes',str(apk),'axs-vps:'+stage]
 q=subprocess.run(scp,capture_output=True,timeout=300)
 if q.returncode:raise RuntimeError(q.stderr.decode(errors='replace'))
 code=HOST.replace('RELEASE',repr(r)).replace('STAGE',repr(stage))
 q=subprocess.run(['C:/Windows/System32/OpenSSH/ssh.exe','-i','D:/Desktop/axs.pem','-o','BatchMode=yes','-o','IdentitiesOnly=yes','axs-vps','python3','-'],input=code.encode(),capture_output=True,timeout=300)
 if q.returncode:raise RuntimeError(q.stdout.decode(errors='replace')+q.stderr.decode(errors='replace'))
 result=json.loads(q.stdout);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
