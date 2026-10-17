import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models import Base, Question, User
from app.services.question_sync.normalize import normalize


@pytest.mark.asyncio
async def test_offline_cli_staging_review_dry_run_and_idempotent_publish(tmp_path):
    directory = Path(__file__).resolve().parents[1]
    url = "sqlite+aiosqlite:///" + (tmp_path / "sync.sqlite").as_posix()
    engine = create_async_engine(url)
    raw = dict(id=100, type=1, stem="肺炎首选药物", options=["甲", "乙"], answer=[0])
    meta = dict(bank_id="10", chapter_id="20", bank_title="内科练习", chapter_title="肺炎")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        question = Question(qid="99", **normalize({**raw, "id": 99}, meta))
        question.bank_group, question.subject_dir, question.system = "综合", "05-内科学", "呼吸系统"
        session.add_all([question, User(id=1, username="admin", password_hash="unused", is_admin=True)])
        await session.commit()
    source = tmp_path / "source.json"
    source.write_text(json.dumps([dict(raw=raw, source_meta=meta)]), encoding="utf-8")
    env = dict(os.environ, MEDKB_DATABASE_URL=url, MEDKB_GLM_API_KEY="", PYTHONIOENCODING="utf-8")

    def run(*args):
        result = subprocess.run([sys.executable, "scripts/sync_questions.py", *map(str, args)],
                                cwd=directory, env=env, capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    assert run("import-json", source)["new"] == 1
    assert len(run("analyze", "--rules-only")["proposals"]) == 1
    report, review = tmp_path / "report.json", tmp_path / "review.json"
    assert run("report", "--output", report, "--review-template", review)["count"] == 1
    decisions = json.loads(review.read_text(encoding="utf-8"))
    assert decisions["decisions"][0]["action"] == "review"
    decisions["decisions"][0].update(action="publish", accept_classification=True, classification_override=dict(
        bank_group="综合", subject_dir="05-内科学", system="呼吸系统", tags=[], reason="人工核对题干为肺炎选药考点"))
    review.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
    assert run("publish", review, "--actor", 1, "--dry-run")["dry_run"]
    async with AsyncSession(engine) as session:
        assert await session.scalar(select(func.count()).select_from(Question)) == 1
    assert run("publish", review, "--actor", 1)["results"][0]["status"] == "applied"
    assert run("publish", review, "--actor", 1)["results"][0]["idempotent"]
    assert run("status")["invalid"] == []
    async with AsyncSession(engine) as session:
        assert await session.scalar(select(func.count()).select_from(Question)) == 2
    await engine.dispose()
