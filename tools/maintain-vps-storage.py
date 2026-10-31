"""Clean Docker build cache on axs-vps without changing or restarting services."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path('/opt/medkb-v2')
SOURCE = ROOT / 'src/backend/app/data/question_evidence_review_queue.json'
DEST = '/srv/app/data/question_evidence_review_queue.json'
LOCK = ROOT / '.qa-recall-publication.lock'


def run(args, timeout=120):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=timeout)


def inspect():
    return json.loads(run(['docker', 'inspect', 'medkb-api']))[0]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_catalog_mount(container):
    mounts = [m for m in container.get('Mounts', []) if m.get('Destination') == DEST]
    if len(mounts) != 1 or mounts[0].get('Source') != str(SOURCE) or mounts[0].get('RW') is not False:
        raise ValueError('Readonly catalog bind mount is not ready; use the separate migration tool')


def state():
    container = inspect()
    validate_catalog_mount(container)
    catalog = run(['docker', 'exec', 'medkb-api', 'cat', DEST])
    health = urllib.request.urlopen('http://127.0.0.1:8899/api/health', timeout=3)
    try:
        health_body = json.loads(health.read())
        if health.status != 200 or health_body.get('status') != 'ok':
            raise ValueError('API health check failed')
    finally:
        health.close()
    return {
        'container_id': container['Id'],
        'image_id': container['Image'],
        'catalog_sha256': digest(catalog),
        'compose_sha256': digest((ROOT / 'src/deploy/docker-compose.yml').read_bytes()),
        'source_sha256': digest(SOURCE.read_bytes()),
        'health': health_body,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Prune Docker build cache and unused old images')
    if not parser.parse_args().apply:
        raise SystemExit('Read docs/storage-workflow.md; explicit --apply is required on axs-vps.')
    with LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = state()
        builder = run(['docker', 'builder', 'prune', '-a', '-f'], timeout=600)
        images = run(['docker', 'image', 'prune', '-a', '-f', '--filter', 'until=24h'], timeout=600)
        after = state()
        if before != after:
            raise ValueError('Cleanup changed service, catalog, mount source, or health state')
        print(json.dumps({
            'stage': 'complete',
            'mode': 'cleanup-only',
            'before': before,
            'after': after,
            'builder': builder.decode('utf-8', 'replace').splitlines()[-1:],
            'images': images.decode('utf-8', 'replace').splitlines()[-1:],
            'disk': run(['df', '-B1', '/']).decode('utf-8', 'replace').splitlines()[-1],
            'completed_at_epoch': int(time.time()),
        }, ensure_ascii=False))


if __name__ == '__main__':
    main()
