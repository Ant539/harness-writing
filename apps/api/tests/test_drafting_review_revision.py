def _create_evidence_ready_section(client) -> tuple[dict, dict, list[dict]]:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Section Drafting Harnesses",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert paper_response.status_code == 201
    paper = paper_response.json()
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    section = next(node for node in outline if node["title"] == "Introduction")

    contract_response = client.post(f"/sections/{section['id']}/generate-contract", json={})
    assert contract_response.status_code == 200
    section = contract_response.json()["section"]

    evidence_response = client.post(
        f"/papers/{paper['id']}/evidence/upload",
        json=[
            {
                "section_id": section["id"],
                "source_type": "paper_summary",
                "source_ref": "smith2024",
                "content": "Evidence-first drafting keeps section claims tied to source material.",
                "citation_key": "smith2024",
                "confidence": 0.9,
                "metadata": {},
            },
            {
                "section_id": section["id"],
                "source_type": "note",
                "source_ref": "note-1",
                "content": "Review comments should become concrete revision tasks.",
                "citation_key": None,
                "confidence": 0.85,
                "metadata": {},
            },
        ],
    )
    assert evidence_response.status_code == 201
    evidence_items = evidence_response.json()
    pack_response = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [item["id"] for item in evidence_items]},
    )
    assert pack_response.status_code == 200
    section = client.get(f"/sections/{section['id']}").json()
    assert section["status"] == "evidence_ready"
    return paper, section, evidence_items


def _draft_section(client, section_id: str) -> dict:
    response = client.post(
        f"/sections/{section_id}/draft",
        json={
            "drafting_instructions": "Keep the placeholder concise.",
            "neighboring_section_context": "Conclusion follows later.",
        },
    )
    assert response.status_code == 200
    return response.json()


def _review_section(client, section_id: str) -> dict:
    response = client.post(
        f"/sections/{section_id}/review",
        json={"review_instructions": "Check traceability and section length."},
    )
    assert response.status_code == 200
    return response.json()


def test_generate_draft_for_evidence_ready_section(client) -> None:
    _, section, evidence_items = _create_evidence_ready_section(client)

    payload = _draft_section(client, section["id"])

    draft = payload["draft"]
    assert payload["section"]["status"] == "drafted"
    assert draft["version"] == 1
    assert draft["status"] == "active"
    assert draft["section_id"] == section["id"]
    assert draft["supported_evidence_ids"] == [item["id"] for item in evidence_items]
    assert "Introduction" in draft["content"]
    assert "[smith2024]" in draft["content"]

    current = client.get(f"/sections/{section['id']}/drafts/current")
    assert current.status_code == 200
    assert current.json()["id"] == draft["id"]


def test_draft_generation_rejects_invalid_and_repeated_flows(client) -> None:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Invalid Draft Guards",
            "paper_type": "conceptual",
            "target_language": "English",
        },
    )
    paper = paper_response.json()
    section = client.post(
        f"/papers/{paper['id']}/sections",
        json={"title": "Introduction", "level": 1, "order_index": 1},
    ).json()

    invalid = client.post(f"/sections/{section['id']}/draft", json={})
    assert invalid.status_code == 400
    assert "evidence_ready" in invalid.json()["detail"]

    _, ready_section, _ = _create_evidence_ready_section(client)
    _draft_section(client, ready_section["id"])
    repeated = client.post(f"/sections/{ready_section['id']}/draft", json={})
    assert repeated.status_code == 409
    assert "revision flow" in repeated.json()["detail"]


def test_review_generation_persists_comments_and_revision_tasks(client) -> None:
    _, section, _ = _create_evidence_ready_section(client)
    draft_payload = _draft_section(client, section["id"])

    review_payload = _review_section(client, section["id"])

    assert review_payload["draft"]["id"] == draft_payload["draft"]["id"]
    assert review_payload["section"]["status"] == "revision_required"
    assert review_payload["comments"]
    assert review_payload["revision_tasks"]
    assert review_payload["revision_tasks"][0]["draft_id"] == draft_payload["draft"]["id"]
    assert review_payload["revision_tasks"][0]["status"] == "active"

    comments_response = client.get(f"/drafts/{draft_payload['draft']['id']}/reviews")
    assert comments_response.status_code == 200
    assert len(comments_response.json()) == len(review_payload["comments"])

    section_reviews = client.get(f"/sections/{section['id']}/reviews")
    assert section_reviews.status_code == 200
    assert len(section_reviews.json()) == len(review_payload["comments"])

    tasks_response = client.get(f"/sections/{section['id']}/revision-tasks")
    assert tasks_response.status_code == 200
    assert len(tasks_response.json()) == len(review_payload["revision_tasks"])


def test_review_requires_current_draft(client) -> None:
    _, section, _ = _create_evidence_ready_section(client)

    response = client.post(f"/sections/{section['id']}/review", json={})

    assert response.status_code == 400
    assert "current draft" in response.json()["detail"]


def test_revision_creates_new_draft_version_and_completes_review_context(client) -> None:
    _, section, _ = _create_evidence_ready_section(client)
    draft_payload = _draft_section(client, section["id"])
    review_payload = _review_section(client, section["id"])

    revision_response = client.post(
        f"/sections/{section['id']}/revise",
        json={"revision_instructions": "Resolve the structured review comments."},
    )

    assert revision_response.status_code == 200
    revision_payload = revision_response.json()
    assert revision_payload["section"]["status"] == "revised"
    assert revision_payload["previous_draft_id"] == draft_payload["draft"]["id"]
    assert revision_payload["draft"]["version"] == 2
    assert revision_payload["draft"]["status"] == "active"
    assert "Revision pass applied" in revision_payload["draft"]["content"]
    assert set(revision_payload["resolved_review_comment_ids"]) == {
        comment["id"] for comment in review_payload["comments"]
    }
    assert set(revision_payload["completed_revision_task_ids"]) == {
        task["id"] for task in review_payload["revision_tasks"]
    }

    drafts = client.get(f"/sections/{section['id']}/drafts").json()
    assert [draft["version"] for draft in drafts] == [1, 2]
    assert drafts[0]["status"] == "superseded"
    assert drafts[1]["status"] == "active"

    comments = client.get(f"/drafts/{draft_payload['draft']['id']}/reviews").json()
    assert all(comment["resolved"] for comment in comments)
    tasks = client.get(f"/sections/{section['id']}/revision-tasks").json()
    assert all(task["status"] == "approved" for task in tasks)


def test_revision_requires_review_comment_or_task_context(client) -> None:
    _, section, _ = _create_evidence_ready_section(client)
    _draft_section(client, section["id"])
    transition = client.post(f"/sections/{section['id']}/transition", json={"status": "reviewed"})
    assert transition.status_code == 200

    response = client.post(f"/sections/{section['id']}/revise", json={})

    assert response.status_code == 400
    assert "review comment or revision task" in response.json()["detail"]
