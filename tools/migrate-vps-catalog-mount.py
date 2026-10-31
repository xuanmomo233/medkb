"""One-time migration from image-owned catalog to a readonly host bind mount."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true', help='Migrate and recreate the API container once')
if not parser.parse_args().apply:
    raise SystemExit('Read docs/storage-workflow.md; explicit --apply is required on axs-vps.')

ROOT = Path('/opt/medkb-v2')
SOURCE = ROOT / 'src/backend/app/data/question_evidence_review_queue.json'
DEST = '/srv/app/data/question_evidence_review_queue.json'
COMPOSE = ROOT / 'src/deploy/docker-compose.yml'
COMPOSE_ARGS = ['docker', 'compose', '--project-directory', str(COMPOSE.parent), '-p', 'deploy', '-f', str(COMPOSE)]
LOCK = ROOT / '.qa-recall-publication.lock'


def run(args, timeout=120):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=timeout)


def inspect():
    return json.loads(run(['docker', 'inspect', 'medkb-api']))[0]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.catalog-mount-', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def healthy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8899/api/health', timeout=3) as response:
            return response.status == 200 and json.loads(response.read()).get('status') == 'ok'
    except Exception:
        return False


with LOCK.open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    initial = inspect()
    existing = [m for m in initial.get('Mounts', []) if m.get('Destination') == DEST]
    if existing:
        if len(existing) == 1 and existing[0].get('Source') == str(SOURCE) and existing[0].get('RW') is False:
            raise SystemExit('Readonly catalog mount is already configured; no migration or restart performed.')
        raise ValueError('Unexpected catalog mount already exists; refusing migration')

    live = run(['docker', 'exec', 'medkb-api', 'cat', DEST])
    if digest(live) != digest(SOURCE.read_bytes()):
        raise ValueError('Host catalog differs from running API catalog; refusing overwrite')
    compose_before = COMPOSE.read_bytes()
    source_before = SOURCE.read_bytes()
    marker = '    volumes:\n'
    text = compose_before.decode('utf-8').replace('\r\n', '\n')
    binding = f'      - {SOURCE}:{DEST}:ro'
    if text.count(marker) != 1 or str(SOURCE) in text:
        raise ValueError('Ambiguous or partially configured API volumes section')
    text = text.replace(marker, marker + binding + '\n', 1)
    image = initial['Image']
    tagged = json.loads(run(['docker', 'image', 'inspect', 'deploy-api']))[0]['Id']
    if tagged != image:
        raise ValueError('deploy-api tag differs from the running image')
    try:
        atomic(SOURCE, live)
        atomic(COMPOSE, text.encode('utf-8'))
        run(COMPOSE_ARGS + ['config', '-q'])
        run(COMPOSE_ARGS + ['up', '-d', '--no-build', '--force-recreate', 'api'])
        after = inspect()
        mounts = [m for m in after.get('Mounts', []) if m.get('Destination') == DEST]
        observed = run(['docker', 'exec', 'medkb-api', 'cat', DEST])
        if (after.get('Image') != image or digest(observed) != digest(live) or not healthy()
                or len(mounts) != 1 or mounts[0].get('Source') != str(SOURCE) or mounts[0].get('RW') is not False):
            raise ValueError('Mounted catalog migration failed health/image/hash verification')
        print(json.dumps({'stage': 'mounted-catalog', 'image_id': image,
                          'catalog_sha256': digest(live), 'health': True}, ensure_ascii=False))
    except BaseException:
        atomic(COMPOSE, compose_before)
        atomic(SOURCE, source_before)
        run(COMPOSE_ARGS + ['up', '-d', '--no-build', '--force-recreate', 'api'])
        raise
