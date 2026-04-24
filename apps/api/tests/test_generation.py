def _create_paper(client, paper_type: str = "conceptual") -> dict:
    response = client.post(
        "/papers",
        json={
            "title": "Controlled Paper Harnesses",
            "paper_type": paper_type,
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_generate_outline_for_new_paper_persists_hierarchy(client) -> None:
    paper = _create_paper(client, "conceptual")

    response = client.post(
        f"/papers/{paper['id']}/generate-outline",
        json={"additional_context": "Focus on implementation readiness.", "target_word_count": 6000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paper"]["status"] == "outline_ready"

    nodes = payload["outline"]
    assert len(nodes) >= 6
    assert {node["title"] for node in nodes} >= {
        "Introduction",
        "Proposed Framework",
        "Workflow Components",
    }

    proposed_framework = next(node for node in nodes if node["title"] == "Proposed Framework")
    workflow_components = next(node for node in nodes if node["title"] == "Workflow Components")
    assert workflow_components["parent_id"] == proposed_framework["id"]
    assert workflow_components["level"] == 2

    outline_response = client.get(f"/papers/{paper['id']}/outline")
    assert outline_response.status_code == 200
    assert len(outline_response.json()["nodes"]) == len(nodes)


def test_generate_outline_rejects_duplicate_generation(client) -> None:
    paper = _create_paper(client, "survey")

    first = client.post(f"/papers/{paper['id']}/generate-outline", json={})
    assert first.status_code == 200

    duplicate = client.post(f"/papers/{paper['id']}/generate-outline", json={})
    assert duplicate.status_code == 409


def test_manual_outline_edit_after_generation(client) -> None:
    paper = _create_paper(client)
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    introduction = next(node for node in outline if node["title"] == "Introduction")
    conclusion = next(node for node in outline if node["title"] == "Conclusion")

    response = client.patch(
        f"/sections/{conclusion['id']}",
        json={
            "title": "Closing Discussion",
            "parent_id": introduction["id"],
            "level": 2,
            "order_index": 99,
        },
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["title"] == "Closing Discussion"
    assert edited["parent_id"] == introduction["id"]
    assert edited["level"] == 2
    assert edited["order_index"] == 99


def test_generate_section_contract_and_manual_edit(client) -> None:
    paper = _create_paper(client, "empirical")
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    methodology = next(node for node in outline if node["title"] == "Methodology")

    response = client.post(
        f"/sections/{methodology['id']}/generate-contract",
        json={"additional_constraints": "Keep the method reproducible."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["section"]["status"] == "contract_ready"
    contract = payload["contract"]
    assert contract["section_id"] == methodology["id"]
    assert "Methodology" in contract["purpose"]
    assert contract["required_evidence_count"] >= 1
    assert contract["length_min"] < contract["length_max"]

    edit = client.patch(
        f"/contracts/{contract['id']}",
        json={
            "tone": "precise academic",
            "required_evidence_count": 2,
            "forbidden_patterns": ["No vague methods claims."],
        },
    )
    assert edit.status_code == 200
    edited_contract = edit.json()
    assert edited_contract["tone"] == "precise academic"
    assert edited_contract["required_evidence_count"] == 2
    assert edited_contract["forbidden_patterns"] == ["No vague methods claims."]


def test_generate_contract_rejects_duplicate_without_force_and_updates_with_force(client) -> None:
    paper = _create_paper(client)
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    section = next(node for node in outline if node["title"] == "Introduction")

    first = client.post(f"/sections/{section['id']}/generate-contract", json={})
    assert first.status_code == 200
    contract_id = first.json()["contract"]["id"]

    duplicate = client.post(f"/sections/{section['id']}/generate-contract", json={})
    assert duplicate.status_code == 409

    forced = client.post(
        f"/sections/{section['id']}/generate-contract",
        json={"force": True, "additional_constraints": "Mention approval checkpoints."},
    )
    assert forced.status_code == 200
    assert forced.json()["contract"]["id"] == contract_id
    assert "Mention approval checkpoints" in forced.json()["contract"]["purpose"]


def test_generate_contract_rejects_invalid_section_status(client) -> None:
    paper = _create_paper(client)
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    section = next(node for node in outline if node["title"] == "Introduction")

    transition = client.post(f"/sections/{section['id']}/transition", json={"status": "contract_ready"})
    assert transition.status_code == 200
    transition = client.post(f"/sections/{section['id']}/transition", json={"status": "evidence_ready"})
    assert transition.status_code == 400

    response = client.post(f"/sections/{section['id']}/generate-contract", json={})
    assert response.status_code == 200
