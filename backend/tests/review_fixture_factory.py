"""Small synthetic structural/HTTP inputs, never a production audit snapshot."""
import hashlib
import json


def structural_review_inputs(context_groups):
    groups = []
    row_id = 1
    for number, members in enumerate(context_groups):
        rows = []
        for index, (qid, anchor) in enumerate(members):
            rows.append({"id": row_id, "qid": qid, "answer": "A", "parse_status": "mapped",
                         "meaning": json.dumps([f"distinct-choice-{number}-{index}"]),
                         "options": [f"choice-{index}", "other"],
                         "source_file": f"synthetic/context-{number}/source-{index}.md",
                         "analysis_preview": "unit-test context marker: " + anchor, "chapter": "synthetic"})
            row_id += 1
        groups.append({"group_id": f"context-{number}", "stem": "synthetic shared prompt",
                       "unparsed_count": 0, "rows": rows})
    for number in range(13):
        rows = []
        for index, choice in enumerate(["甲,乙", "甲、乙"]):
            rows.append({"id": row_id, "qid": f"punct-{number}-{index}", "answer": "A",
                         "parse_status": "mapped", "meaning": json.dumps([choice]),
                         "options": [choice, "丙"], "source_file": f"synthetic/punctuation-{number}-{index}.md",
                         "analysis_preview": "synthetic punctuation only", "chapter": "synthetic"})
            row_id += 1
        groups.append({"group_id": f"punctuation-{number}", "stem": "synthetic punctuation prompt",
                       "unparsed_count": 0, "rows": rows})
    ledger = {"postgres_snapshot": "1:1:", "groups": [
        {"group_id": group["group_id"], "content_sha256": hashlib.sha256(json.dumps(
            group["rows"], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
         "members": [{"database_id": r["id"], "qid": r["qid"]} for r in group["rows"]],
         "cases": [{"case_id": "synthetic-unit-case"}]} for group in groups]}
    return {"postgres_snapshot": "1:1:", "rule_version": "synthetic-structural-unit-input", "conflicts": groups}, ledger


def relation_alias_inputs():
    # Only the topology matters: three canonical endpoints each have an alias.
    pairs = [(3726, 7827), (3726, 9786), (69974, 70150), (101, 102),
             (103, 104), (105, 106), (107, 108)]
    plan = {"relations": [{"endpoints": [{"database_id": a}, {"database_id": b}]} for a, b in pairs]}
    identities = [{"canonical_id": 3726, "members": [{"id": 1218}, {"id": 3726}]},
                  {"canonical_id": 70150, "members": [{"id": 5010}, {"id": 70150}]}]
    return plan, identities


def write_http_publication_inputs(folder, plan_names, relations_name):
    questions = [{"database_id": i, "proposed_question_status": "disputed" if i <= 26 else "normal"}
                 for i in range(1, 74)]
    for index, name in enumerate(plan_names):
        selected = questions[index * 25:(index + 1) * 25]
        (folder / name).write_text(json.dumps({"fixture_only": True, "questions": selected, "relations": []}), encoding="utf-8")
    relations = {"fixture_only": True, "relations": relation_alias_inputs()[0]["relations"][:5]}
    (folder / relations_name).write_text(json.dumps(relations), encoding="utf-8")
    return relations
