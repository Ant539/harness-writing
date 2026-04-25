def _create_reviewed_section(client) -> tuple[dict, dict, dict]:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Approval Harnesses",
            "paper_type": "conceptual",
            "target_language": "English",
        },
    )
    assert paper_response.status_code == 201
    paper = paper_response.json()
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    section = next(node for node in outline if node["title"] == "Introduction")
    client.post(f"/sections/{section['id']}/generate-contract", json={})
    evidence = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": section["id"],
            "source_type": "note",
            "content": "Approval workflows need current drafts.",
            "confidence": 0.9,
            "metadata": {},
        },
    ).json()
    client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [evidence["id"]]},
    )
    draft = client.post(f"/sections/{section['id']}/draft", json={}).json()["draft"]
    reviewed = client.post(f"/sections/{section['id']}/transition", json={"status": "reviewed"})
    assert reviewed.status_code == 200
    return paper, reviewed.json(), draft


def test_section_approval_request_approve_lock_and_unlock(client) -> None:
    _, section, draft = _create_reviewed_section(client)

    request = client.post(
        f"/sections/{section['id']}/approval-request",
        json={"requested_by": "operator", "note": "Ready for approval."},
    )
    assert request.status_code == 200
    assert request.json()["status"] == "pending"
    assert request.json()["draft_id"] == draft["id"]

    approve = client.post(
        f"/sections/{section['id']}/approve",
        json={"decided_by": "lead", "note": "Approved."},
    )

    assert approve.status_code == 200
    assert approve.json()["section"]["status"] == "locked"
    assert approve.json()["approval"]["status"] == "approved"
    assert approve.json()["approval"]["draft_id"] == draft["id"]

    locked_changes = client.post(
        f"/sections/{section['id']}/request-changes",
        json={"decided_by": "lead", "note": "Too late while locked."},
    )
    assert locked_changes.status_code == 400
    assert "Unlock the section" in locked_changes.json()["detail"]

    approvals = client.get(f"/sections/{section['id']}/approvals")
    assert approvals.status_code == 200
    assert [item["status"] for item in approvals.json()] == ["superseded", "approved"]

    unlock = client.post(
        f"/sections/{section['id']}/unlock",
        json={"decided_by": "lead", "note": "Unlock for another pass."},
    )
    assert unlock.status_code == 200
    assert unlock.json()["section"]["status"] == "reviewed"
    assert unlock.json()["approval"]["status"] == "unlocked"


def test_section_approval_request_changes_supersedes_pending_request(client) -> None:
    _, section, draft = _create_reviewed_section(client)

    request = client.post(
        f"/sections/{section['id']}/approval-request",
        json={"requested_by": "operator", "note": "Please review."},
    )
    assert request.status_code == 200

    changes = client.post(
        f"/sections/{section['id']}/request-changes",
        json={"decided_by": "lead", "note": "Needs a clearer claim."},
    )

    assert changes.status_code == 200
    assert changes.json()["section"]["status"] == "reviewed"
    assert changes.json()["approval"]["status"] == "changes_requested"
    assert changes.json()["approval"]["draft_id"] == draft["id"]

    approvals = client.get(f"/sections/{section['id']}/approvals")
    assert [item["status"] for item in approvals.json()] == ["superseded", "changes_requested"]


def test_section_approval_requires_reviewed_or_revised_without_unresolved_comments(client) -> None:
    paper, section, draft = _create_reviewed_section(client)
    other = client.post(
        f"/papers/{paper['id']}/sections",
        json={"title": "Unreviewed", "level": 1, "order_index": 99},
    ).json()
    client.post(
        f"/sections/{other['id']}/drafts",
        json={
            "kind": "section_draft",
            "version": 1,
            "content": "Draft without review.",
            "supported_evidence_ids": [],
            "status": "active",
        },
    )

    unreviewed = client.post(f"/sections/{other['id']}/approve", json={})
    assert unreviewed.status_code == 400
    assert "reviewed or revised" in unreviewed.json()["detail"]

    comment = client.post(
        f"/drafts/{draft['id']}/reviews",
        json={
            "comment_type": "logic_gap",
            "severity": "medium",
            "comment": "Still needs a fix.",
            "suggested_action": "Fix before approval.",
            "resolved": False,
        },
    )
    assert comment.status_code == 201
    unresolved = client.post(f"/sections/{section['id']}/approve", json={})
    assert unresolved.status_code == 400
    assert "resolving active review comments" in unresolved.json()["detail"]


def test_section_approval_resolves_approval_checkpoint(client) -> None:
    paper, section, _ = _create_reviewed_section(client)
    run = client.post(f"/papers/{paper['id']}/workflow-runs", json={"auto_execute": False}).json()[
        "workflow_run"
    ]
    checkpoint = client.post(
        f"/papers/{paper['id']}/workflow-checkpoints",
        json={
            "workflow_run_id": run["id"],
            "section_id": section["id"],
            "checkpoint_type": "approval_required",
            "reason": "Approve before export.",
            "required_actions": ["Approve the section."],
        },
    ).json()

    approval = client.post(
        f"/sections/{section['id']}/approve",
        json={"workflow_checkpoint_id": checkpoint["id"], "decided_by": "lead"},
    )
    assert approval.status_code == 200
    assert approval.json()["approval"]["workflow_checkpoint_id"] == checkpoint["id"]

    checkpoints = client.get(f"/papers/{paper['id']}/workflow-checkpoints").json()
    assert checkpoints[0]["status"] == "resolved"
    assert checkpoints[0]["metadata"]["approval_resolution"] == "Section approved and locked."
