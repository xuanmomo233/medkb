#!/bin/sh
# Install at /opt/medkb-v2/question-sync/run.sh; no credentials in this script.
set -eu
umask 077
base=/opt/medkb-v2/question-sync
mode=${1:-cycle}
case "$mode" in cycle|probe|status) ;; *) exit 64 ;; esac
exec 9>/run/lock/medkb-question-sync.lock
flock -n 9 || exit 0
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
mkdir -p "$base/logs"
log="$base/logs/$mode.log"
image=medkb-question-sync:current
invoke() {
    docker run --rm --name medkb-question-sync-job --network 1panel-network \
        --memory=900m --cpus=1 --env-file "$base/.env" "$image" "$@"
}
rc=0
configured=1
if [ "$mode" != status ]; then
    python3 - "$base/.env" <<'PY' || configured=0
from pathlib import Path
import sys
present = any(line.startswith('MEDKB_WCYK_TOKEN=') and line.partition('=')[2].strip()
              for line in Path(sys.argv[1]).read_text().splitlines())
raise SystemExit(0 if present else 1)
PY
fi
if [ "$configured" -eq 0 ]; then
    printf '%s\n' '等待配置上游登录凭据 MEDKB_WCYK_TOKEN' >"$log"
    rc=78
elif [ "$mode" = cycle ]; then
    invoke catalog >"$log" 2>&1 || rc=$?
    if [ "$rc" -eq 0 ]; then
        invoke analyze --limit 50 >>"$log" 2>&1 || rc=$?
    fi
else
    invoke "$mode" >"$log" 2>&1 || rc=$?
fi
python3 - "$base/status.json" "$mode" "$started" "$rc" "$image" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json, os, sys
path, mode, started, code, image = sys.argv[1:]
target = Path(path)
temporary = target.with_suffix('.new')
data = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
state = 'waiting_credentials' if code == '78' else 'succeeded' if code == '0' else 'failed'
data[mode] = dict(state=state, started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
    exit_code=int(code), image=image, log=f'logs/{mode}.log')
temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
os.replace(temporary, target)
PY
cat "$log"
exit "$rc"
