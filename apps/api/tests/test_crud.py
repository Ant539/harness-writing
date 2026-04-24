def test_core_crud_flow(client) -> None:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Harness Writing for Academic Papers",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert paper_response.status_code == 201
    paper = paper_response.json()
    assert paper["status"] == "idea"

    section_response = client.post(
        f"/papers/{paper['id']}/sections",
        json={
            "title": "Introduction",
            "level": 1,
            "goal": "Frame the controlled writing workflow.",
            "expected_claims": ["Section-centric writing is easier to verify."],
            "word_budget": 900,
            "order_index": 1,
        },
    )
    assert section_response.status_code == 201
    section = section_response.json()
    assert section["status"] == "planned"

    invalid_transition = client.post(
        f"/sections/{section['id']}/transition",
        json={"status": "drafted"},
    )
    assert invalid_transition.status_code == 400

    contract_response = client.post(
        f"/sections/{section['id']}/contract",
        json={
            "purpose": "Explain the paper's motivation.",
            "questions_to_answer": ["Why does the workflow need constraints?"],
            "required_claims": ["Evidence-first writing reduces unsupported claims."],
            "required_evidence_count": 1,
        },
    )
    assert contract_response.status_code == 201

    evidence_response = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": section["id"],
            "source_type": "note",
            "source_ref": "user-note-1",
            "content": "The user wants section-level traceability.",
            "citation_key": None,
            "confidence": 0.9,
            "metadata": {"origin": "test"},
        },
    )
    assert evidence_response.status_code == 201
    evidence = evidence_response.json()
    assert evidence["metadata"] == {"origin": "test"}

    pack_response = client.post(
        f"/sections/{section['id']}/evidence-packs",
        json={
            "evidence_item_ids": [evidence["id"]],
            "coverage_summary": "Covers the traceability motivation.",
            "open_questions": [],
        },
    )
    assert pack_response.status_code == 201
    assert pack_response.json()["evidence_item_ids"] == [evidence["id"]]

    draft_response = client.post(
        f"/sections/{section['id']}/drafts",
        json={
            "kind": "section_draft",
            "version": 1,
            "content": "Draft placeholder with traceability.",
            "supported_evidence_ids": [evidence["id"]],
            "status": "draft",
        },
    )
    assert draft_response.status_code == 201
    draft = draft_response.json()

    review_response = client.post(
        f"/drafts/{draft['id']}/reviews",
        json={
            "comment_type": "style_issue",
            "severity": "medium",
            "comment": "Tighten the academic tone.",
            "suggested_action": "Revise wording.",
            "resolved": False,
        },
    )
    assert review_response.status_code == 201
    review = review_response.json()

    resolve_response = client.post(f"/reviews/{review['id']}/resolve", json={})
    assert resolve_response.status_code == 200
    assert resolve_response.json()["resolved"] is True

    task_response = client.post(
        f"/sections/{section['id']}/revision-tasks",
        json={
            "draft_id": draft["id"],
            "task_description": "Tighten wording.",
            "priority": "medium",
            "status": "active",
        },
    )
    assert task_response.status_code == 201

    style_response = client.post(
        f"/papers/{paper['id']}/style-guide",
        json={
            "tone": "academic",
            "voice": "clear",
            "citation_style": "APA",
            "terminology_preferences": {"LLM": "large language model"},
            "forbidden_patterns": [],
            "format_rules": {},
        },
    )
    assert style_response.status_code == 201
