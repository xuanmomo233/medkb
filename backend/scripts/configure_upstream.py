"""Validate fresh authorized login material and atomically update worker credentials."""
import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.question_sync.auth_material import load_material  # noqa: E402
from app.services.question_sync.upstream import WcykClient  # noqa: E402


async def configure(input_file: Path, env_file: Path, *, qid=235290, factory=WcykClient):
    if not env_file.is_file():
        raise ValueError("同步环境文件不存在，需先完成运行环境部署")
    token = load_material(input_file.read_text(encoding="utf-8-sig"))
    client = factory(token)
    try:
        payload = await client.request("/api/question", {"id": qid})
        if not payload.get("data"):
            raise ValueError("登录验证没有返回题目，配置保持原样")
    finally:
        await client.close()
    lines = [line for line in env_file.read_text(encoding="utf-8").splitlines() if not line.startswith("MEDKB_WCYK_TOKEN=")]
    temporary = env_file.with_name(env_file.name + ".auth-new")
    created = False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(lines) + "\nMEDKB_WCYK_TOKEN=" + token + "\n")
        os.replace(temporary, env_file)
    finally:
        if created and temporary.exists():
            temporary.unlink()
    return {"authenticated": True, "credential_installed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--qid", type=int, default=235290)
    args = parser.parse_args()
    try:
        import json
        print(json.dumps(asyncio.run(configure(args.input_file, args.env_file, qid=args.qid))))
    except Exception as error:
        print(f"登录材料验证失败：{type(error).__name__}；原配置未替换，未输出令牌。", file=sys.stderr)
        raise SystemExit(1)
