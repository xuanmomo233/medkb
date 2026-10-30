import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.services.option_labels import import_options, labels_for, parse_markdown_options

OPTIONS = [f"选项{i}" for i in range(10)]


@pytest.mark.parametrize("labels", [["A", "A"], ["A"], ["A", "a"], ["A", "AA"], ["A", "１"]])
def test_explicit_invalid_labels_never_fall_back(labels):
    with pytest.raises(ValueError):
        labels_for(["甲", "乙"], labels)


def test_legacy_empty_labels_fallback_through_z():
    assert labels_for(OPTIONS, None) == list("ABCDEFGHIJ")
    assert labels_for(OPTIONS, []) == list("ABCDEFGHIJ")
    assert labels_for(list(range(26)), [])[-1] == "Z"


@pytest.mark.parametrize("explicit", [None, [], "[]", ["A", "J", "K", "L"]])
def test_nucleotide_combinations_are_option_bodies_not_embedded_labels(explicit):
    bodies = ["A、G", "G、A", "U、C", "U、A"]
    expected = explicit if isinstance(explicit, list) and explicit else list("ABCD")
    assert import_options(bodies, explicit) == (bodies, expected)


@pytest.mark.parametrize("prefix", ["- {label}、 ", "* {label}、 ", "{label}. ", "{label}) ", "{label}） "])
def test_real_markdown_labels_preserve_inner_nucleotide_combinations(prefix):
    bodies = ["A、G", "G、A", "U、C", "U、A"]
    labels = list("AJKL")
    lines = [prefix.format(label=label)+body for label, body in zip(labels, bodies)]
    assert parse_markdown_options("\n".join(lines)) == (bodies, labels)
    assert import_options(lines, labels) == (bodies, labels)


def test_bare_nucleotide_combinations_are_not_accepted_as_markdown_labels():
    with pytest.raises(ValueError, match="明确字母标签"):
        parse_markdown_options("A、G\nG、A\nU、C\nU、A")


def test_real_legacy_table_additive_migration_preserves_data_and_default():
    migration = Path(__file__).resolve().parents[1] / "alembic/versions/20261018_01_option_labels.py"
    spec = importlib.util.spec_from_file_location("label_migration", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE questions (id INTEGER PRIMARY KEY, answer TEXT NOT NULL)"))
        conn.execute(sa.text("CREATE TABLE attempts (id INTEGER PRIMARY KEY, picked VARCHAR(16) NOT NULL)"))
        conn.execute(sa.text("INSERT INTO attempts VALUES (1, 'ABC')"))
        conn.execute(sa.text("INSERT INTO questions VALUES (1, 'J、K')"))
        module.op = Operations(MigrationContext.configure(conn))
        module.upgrade()
        assert conn.execute(sa.text("SELECT answer, option_labels FROM questions WHERE id=1")).one() == ("J、K", "[]")
        conn.execute(sa.text("INSERT INTO questions (id,answer) VALUES (2,'A')"))
        assert conn.execute(sa.text("SELECT option_labels FROM questions WHERE id=2")).scalar_one() == "[]"
        assert sa.inspect(conn).get_columns("attempts")[1]["type"].length == 26
        conn.execute(sa.text("INSERT INTO attempts VALUES (2, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"))
        module.downgrade()
        assert conn.execute(sa.text("SELECT answer FROM questions WHERE id=1")).scalar_one() == "J、K"
        assert conn.execute(sa.text("SELECT picked FROM attempts WHERE id=2")).scalar_one() == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        assert sa.inspect(conn).get_columns("attempts")[1]["type"].length == 26
