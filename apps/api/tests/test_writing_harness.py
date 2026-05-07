def test_quick_rewrite_uses_lightweight_workflow(client) -> None:
    response = client.post(
        "/writing-harness/runs",
        json={
            "user_input": "Make this email more polite.",
            "source_text": "Send me the report today.",
            "tone": "polite",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["task_type"] == "quick_rewrite"
    assert payload["state"] == "final_ready"
    assert payload["artifacts"]["outline"] is None
    assert payload["artifacts"]["claim_evidence_map"] is None
    assert payload["artifacts"]["review_report"] is None
    assert payload["artifacts"]["final_output"].startswith("Thank you for your time.")
    states = [item["state"] for item in payload["state_history"]]
    assert "paper_outline_ready" not in states


def test_structured_blog_generates_brief_outline_review_and_revision(client) -> None:
    response = client.post(
        "/writing-harness/runs",
        json={"user_input": "Help me write a blog about AI agent evaluation."},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["task_type"] == "structured_writing"
    artifacts = payload["artifacts"]
    assert artifacts["writing_brief"]["research_required"] is False
    assert artifacts["outline"]["sections"]
    assert artifacts["review_report"]["rubric_scores"]["structure"] > 0
    assert artifacts["revision_plan"]["from_version"] == 1
    assert artifacts["changelog"]["version_to"] == 2
    assert "Revision note" in artifacts["final_output"]


def test_academic_paper_workflow_marks_missing_sources_and_claim_risks(client) -> None:
    response = client.post(
        "/writing-harness/runs",
        json={
            "user_input": (
                "Help me write an academic paper about LLM agent evaluation for a workshop, "
                "with related work and method sections."
            ),
            "target_venue": "Workshop",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["task_type"] == "academic_paper"
    assert payload["state"] == "final_paper_ready"

    artifacts = payload["artifacts"]
    assert artifacts["academic_brief"]["citation_required"] is True
    assert artifacts["claim_evidence_map"]["claims"]
    assert artifacts["claim_evidence_map"]["claims"][0]["unsupported_risk"] == "high"
    assert artifacts["source_notes"] == []
    assert "[UNSUPPORTED_CLAIM: source required]" in artifacts["draft"]["content"]
    assert artifacts["review_report"]["blocking_issues"]
    assert artifacts["revision_plan"]["must_fix"]
    assert any("No source notes" in warning for warning in artifacts["warnings"])

    states = [item["state"] for item in payload["state_history"]]
    assert "academic_briefing" in states
    assert "claim_map_ready" in states
    assert "citation_checking" in states
    assert "claim_evidence_checking" in states


def test_writing_harness_run_is_persisted_and_readable(client) -> None:
    created = client.post(
        "/writing-harness/runs",
        json={"user_input": "Write a short announcement for a product update."},
    )
    assert created.status_code == 201
    run_id = created.json()["id"]

    fetched = client.get(f"/writing-harness/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run_id

    listed = client.get("/writing-harness/runs")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == run_id


def test_academic_paper_can_persist_to_existing_paper_harness_store(client) -> None:
    response = client.post(
        "/writing-harness/runs",
        json={
            "user_input": (
                "Help me write an academic paper about LLM agent evaluation for a workshop, "
                "research question: How should LLM agent evaluation harnesses represent writing quality?"
            ),
            "source_text": "Evaluation harnesses should preserve task context, evidence, and review traces.",
            "target_venue": "Workshop",
            "persist_to_paper_harness": True,
            "paper_harness_pipeline": {
                "generate_contracts": True,
                "extract_evidence": True,
                "build_evidence_packs": True,
                "generate_section_drafts": True,
                "assemble_manuscript": True,
                "export_formats": ["markdown"],
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    paper_harness = payload["metadata"]["paper_harness"]
    assert paper_harness["paper_id"]
    assert paper_harness["outline_node_ids"]
    assert paper_harness["source_material_ids"]
    assert paper_harness["contract_ids"]
    assert paper_harness["evidence_item_ids"]
    assert paper_harness["evidence_pack_ids"]
    assert paper_harness["draft_ids"]
    assert paper_harness["manuscript_id"]
    assert paper_harness["export_ids"]
    assert paper_harness["pipeline_errors"] == []
    assert "PaperHarnessBridge" in payload["metadata"]["role_modules"]

    paper = client.get(f"/papers/{paper_harness['paper_id']}")
    assert paper.status_code == 200
    assert paper.json()["status"] == "assembly_ready"

    outline = client.get(f"/papers/{paper_harness['paper_id']}/outline")
    assert outline.status_code == 200
    assert len(outline.json()["nodes"]) == len(paper_harness["outline_node_ids"])

    export_response = client.get(f"/papers/{paper_harness['paper_id']}/exports")
    assert export_response.status_code == 200
    assert export_response.json()[0]["id"] == paper_harness["export_ids"][0]
