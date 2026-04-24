def _create_paper_with_contract_section(client) -> tuple[dict, dict, dict]:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Evidence First Harnesses",
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
    return paper, contract_response.json()["section"], contract_response.json()["contract"]


def test_source_material_registration_and_extraction(client) -> None:
    paper, section, _ = _create_paper_with_contract_section(client)

    source_response = client.post(
        f"/papers/{paper['id']}/sources",
        json={
            "source_type": "paper_summary",
            "title": "Workflow Summary",
            "source_ref": "smith2024",
            "content": "Evidence-first workflows reduce unsupported claims. Section review catches gaps.",
            "citation_key": "smith2024",
            "metadata": {"kind": "summary"},
        },
    )
    assert source_response.status_code == 201
    source = source_response.json()
    assert source["metadata"] == {"kind": "summary"}

    extraction_response = client.post(
        f"/sources/{source['id']}/extract-evidence",
        json={"section_id": section["id"]},
    )
    assert extraction_response.status_code == 200
    items = extraction_response.json()["items"]
    assert len(items) == 2
    assert items[0]["paper_id"] == paper["id"]
    assert items[0]["section_id"] == section["id"]
    assert items[0]["citation_key"] == "smith2024"
    assert items[0]["metadata"]["source_material_id"] == source["id"]


def test_manual_evidence_item_creation_and_edit(client) -> None:
    paper, section, _ = _create_paper_with_contract_section(client)

    create_response = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": section["id"],
            "source_type": "note",
            "source_ref": "note-1",
            "content": "Original evidence text.",
            "citation_key": None,
            "confidence": 0.7,
            "metadata": {"origin": "manual"},
        },
    )
    assert create_response.status_code == 201
    item = create_response.json()

    update_response = client.patch(
        f"/evidence/{item['id']}",
        json={
            "content": "Edited evidence text.",
            "confidence": 0.95,
            "metadata": {"origin": "manual", "edited": True},
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["content"] == "Edited evidence text."
    assert updated["confidence"] == 0.95
    assert updated["metadata"] == {"origin": "manual", "edited": True}


def test_build_evidence_pack_moves_section_to_evidence_ready(client) -> None:
    paper, section, _ = _create_paper_with_contract_section(client)
    upload_response = client.post(
        f"/papers/{paper['id']}/evidence/upload",
        json=[
            {
                "section_id": section["id"],
                "source_type": "note",
                "source_ref": "note-1",
                "content": "Evidence-first harnesses need section contracts.",
                "confidence": 0.9,
                "metadata": {},
            },
            {
                "section_id": None,
                "source_type": "paper_summary",
                "source_ref": "paper-1",
                "content": "Review checkpoints help detect unsupported claims.",
                "citation_key": "paper1",
                "confidence": 0.8,
                "metadata": {},
            },
        ],
    )
    assert upload_response.status_code == 201
    evidence_ids = [item["id"] for item in upload_response.json()]

    pack_response = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={
            "candidate_evidence_item_ids": evidence_ids,
            "notes": "Prefer contract-related evidence.",
        },
    )
    assert pack_response.status_code == 200
    payload = pack_response.json()
    assert payload["section_id"] == section["id"]
    assert payload["pack"]["evidence_item_ids"]
    assert "Selected" in payload["pack"]["coverage_summary"]

    section_response = client.get(f"/sections/{section['id']}")
    assert section_response.status_code == 200
    assert section_response.json()["status"] == "evidence_ready"


def test_evidence_pack_duplicate_requires_force_and_force_rebuilds(client) -> None:
    paper, section, _ = _create_paper_with_contract_section(client)
    items = client.post(
        f"/papers/{paper['id']}/evidence/upload",
        json=[
            {
                "section_id": section["id"],
                "source_type": "note",
                "content": "First evidence item for the section.",
                "confidence": 0.8,
                "metadata": {},
            },
            {
                "section_id": section["id"],
                "source_type": "note",
                "content": "Second evidence item for rebuilding.",
                "confidence": 0.8,
                "metadata": {},
            },
        ],
    ).json()

    first = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [items[0]["id"]]},
    )
    assert first.status_code == 200
    pack_id = first.json()["pack"]["id"]

    duplicate = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [items[1]["id"]]},
    )
    assert duplicate.status_code == 409

    forced = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [items[1]["id"]], "force": True},
    )
    assert forced.status_code == 200
    assert forced.json()["pack"]["id"] == pack_id
    assert forced.json()["pack"]["evidence_item_ids"] == [items[1]["id"]]


def test_manual_add_and_remove_evidence_pack_membership(client) -> None:
    paper, section, _ = _create_paper_with_contract_section(client)
    items = client.post(
        f"/papers/{paper['id']}/evidence/upload",
        json=[
            {
                "section_id": section["id"],
                "source_type": "note",
                "content": "Initial pack item.",
                "confidence": 0.8,
                "metadata": {},
            },
            {
                "section_id": section["id"],
                "source_type": "note",
                "content": "Manually added item.",
                "confidence": 0.8,
                "metadata": {},
            },
        ],
    ).json()
    pack = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [items[0]["id"]]},
    ).json()["pack"]

    add_response = client.post(
        f"/evidence-packs/{pack['id']}/items",
        json={"evidence_item_id": items[1]["id"]},
    )
    assert add_response.status_code == 200
    assert add_response.json()["evidence_item_ids"] == [items[0]["id"], items[1]["id"]]

    remove_response = client.delete(f"/evidence-packs/{pack['id']}/items/{items[0]['id']}")
    assert remove_response.status_code == 200
    assert remove_response.json()["evidence_item_ids"] == [items[1]["id"]]

    last_remove = client.delete(f"/evidence-packs/{pack['id']}/items/{items[1]['id']}")
    assert last_remove.status_code == 400


def test_invalid_evidence_ready_transition_requires_pack(client) -> None:
    _, section, _ = _create_paper_with_contract_section(client)

    response = client.post(f"/sections/{section['id']}/transition", json={"status": "evidence_ready"})

    assert response.status_code == 400
    assert "active evidence pack" in response.json()["detail"]


def test_build_evidence_pack_requires_contract(client) -> None:
    paper_response = client.post(
        "/papers",
        json={
            "title": "Evidence Contract Guards",
            "paper_type": "conceptual",
            "target_language": "English",
        },
    )
    paper = paper_response.json()
    section = client.post(
        f"/papers/{paper['id']}/sections",
        json={"title": "Introduction", "level": 1, "order_index": 1},
    ).json()
    evidence = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "source_type": "note",
            "content": "Evidence without a contract should not unlock the section.",
            "confidence": 0.8,
            "metadata": {},
        },
    ).json()

    response = client.post(
        f"/sections/{section['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [evidence["id"]]},
    )

    assert response.status_code == 400
    assert "contract" in response.json()["detail"]
