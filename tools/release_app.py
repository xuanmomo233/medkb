"""Build a signed APK with monotonic version and installed-package certificate gates."""
import argparse,hashlib,json,re,shutil,subprocess,os
from pathlib import Path

def run(args,cwd=None,log=None):
    proc=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if log:log.write_text(proc.stdout+proc.stderr,encoding='utf-8')
    if proc.returncode:raise RuntimeError(proc.stdout[-3000:]+proc.stderr[-3000:])
    return proc.stdout

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','flutter','android-sdk','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--build',type=int,required=True);p.add_argument('--name',required=True)
    p.add_argument('--previous',type=Path,help='reuse an already downloaded installed APK after checking the live SHA')
    p.add_argument('--gradle-home',type=Path,help='isolated build cache; never delete the user cache')
    p.add_argument('--pub-cache',type=Path,help='ASCII-only Pub cache for reproducible Windows Kotlin paths')
    p.add_argument('--temp-dir',type=Path)
    p.add_argument('--artifact',type=Path,help='verify a previously completed build without rebuilding')
    p.add_argument('--source-base',help='source baseline commit recorded in the release receipt')
    a=p.parse_args();a.source=a.source.resolve()
    os.environ['ANDROID_HOME']=str(a.android_sdk.resolve())
    os.environ['ANDROID_SDK_ROOT']=str(a.android_sdk.resolve())
    if a.gradle_home:os.environ['GRADLE_USER_HOME']=str(a.gradle_home.resolve())
    if a.pub_cache:os.environ['PUB_CACHE']=str(a.pub_cache.resolve())
    if a.temp_dir:
        a.temp_dir.mkdir(parents=True,exist_ok=True)
        os.environ['TEMP']=os.environ['TMP']=str(a.temp_dir.resolve())
    if a.output.exists():raise ValueError('release output must be a new directory')
    version=json.loads(run(['curl.exe','--fail','--silent','--show-error','https://luck.021209.xyz/api/version']))
    if a.build<=version['build']:raise ValueError('versionCode must increase')
    pub=(a.source/'pubspec.yaml').read_text(encoding='utf-8')
    code=(a.source/'lib/api.dart').read_text(encoding='utf-8')
    if f'version: {a.name}+{a.build}' not in pub or not re.search(r'appBuild\s*=\s*'+str(a.build)+r'\b',code):
        raise ValueError('pubspec, appBuild and requested version must agree')
    if not (a.source/'android/app/key.properties').is_file():raise ValueError('release signing configuration missing')
    tools=sorted((a.android_sdk/'build-tools').iterdir(),key=lambda x:tuple(int(v) for v in x.name.split('.')))
    apksigner=tools[-1]/'apksigner.bat';aapt=tools[-1]/'aapt.exe'
    a.output.mkdir(parents=True)
    old=a.output/'previous.apk'
    if a.previous:old=a.previous.resolve()
    else:run(['curl.exe','--fail','--silent','--show-error','--location','https://luck.021209.xyz/app.apk','--output',old])
    if sha(old)!=version['apk_sha256']:raise ValueError('installed APK SHA mismatch')
    old_sig=run([apksigner,'verify','--verbose','--print-certs',old])
    if not a.artifact:
        run([a.flutter,'build','apk','--release','--build-name',a.name,'--build-number',a.build],a.source,a.output/'build.log')
    artifact=a.artifact.resolve() if a.artifact else a.source/'build/app/outputs/flutter-apk/app-release.apk'
    new_sig=run([apksigner,'verify','--verbose','--print-certs','--min-sdk-version','21',artifact])
    cert=lambda value:re.search(r'certificate SHA-256 digest:\s*(\S+)',value).group(1)
    if cert(old_sig)!=cert(new_sig):raise ValueError('APK signer differs from installed release')
    if not all(re.search(r'Verified using '+v+r' scheme.*: true',new_sig) for v in ['v1','v2']):
        raise ValueError('APK requires v1 and v2 signatures')
    badging=run([aapt,'dump','badging',artifact])
    if f"versionCode='{a.build}'" not in badging or f"versionName='{a.name}'" not in badging:
        raise ValueError('APK embedded version mismatch')
    target=a.output/f'app-release-build{a.build}.apk';shutil.copyfile(artifact,target)
    receipt={'build':a.build,'version':a.name,'apk':str(target),'bytes':target.stat().st_size,
        'sha256':sha(target),'previous_build':version['build'],'previous_apk_sha256':sha(old),
        'signer_sha256':cert(new_sig),'signer_matches':True,'v1_v2_verified':True,
        'real_device_upgrade_test':'not_performed_no_device'}
    source_files=list((a.source/'lib').rglob('*.dart'))+[a.source/p for p in ['pubspec.yaml','pubspec.lock','android/app/build.gradle','android/gradle.properties','android/settings.gradle']]
    source_hashes={p.relative_to(a.source).as_posix():sha(p) for p in source_files}
    receipt['source_fingerprint']=hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
    receipt['source_base_commit']=a.source_base
    (a.output/'release.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':main()
