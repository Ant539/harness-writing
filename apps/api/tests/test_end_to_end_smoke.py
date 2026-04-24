def test_documented_happy_path_from_paper_to_export(client) -> None:
    paper_response = client.post(
        "/papers",
        json={
            "title": "End To End Harness",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert paper_response.status_code == 201
    paper = paper_response.json()

    outline_response = client.post(f"/papers/{paper['id']}/generate-outline", json={})
    assert outline_response.status_code == 200
    introduction = next(
        node for node in outline_response.json()["outline"] if node["title"] == "Introduction"
    )

    contract_response = client.post(f"/sections/{introduction['id']}/generate-contract", json={})
    assert contract_response.status_code == 200

    evidence_response = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": introduction["id"],
            "source_type": "paper_summary",
            "source_ref": "smoke-source",
            "content": "A controlled writing harness keeps evidence attached to section drafts.",
            "citation_key": "smoke2026",
            "confidence": 0.9,
            "metadata": {"test": "end-to-end"},
        },
    )
    assert evidence_response.status_code == 201
    evidence = evidence_response.json()

    pack_response = client.post(
        f"/sections/{introduction['id']}/build-evidence-pack",
        json={"candidate_evidence_item_ids": [evidence["id"]]},
    )
    assert pack_response.status_code == 200

    draft_response = client.post(
        f"/sections/{introduction['id']}/draft",
        json={"drafting_instructions": "Keep the smoke draft deterministic."},
    )
    assert draft_response.status_code == 200
    first_draft = draft_response.json()["draft"]

    review_response = client.post(
        f"/sections/{introduction['id']}/review",
        json={"review_instructions": "Create deterministic review context."},
    )
    assert review_response.status_code == 200
    assert review_response.json()["comments"]

    revision_response = client.post(
        f"/sections/{introduction['id']}/revise",
        json={"revision_instructions": "Address the smoke review context."},
    )
    assert revision_response.status_code == 200
    revised = revision_response.json()["draft"]
    assert revised["version"] == first_draft["version"] + 1

    assembly_response = client.post(f"/papers/{paper['id']}/assemble", json={})
    assert assembly_response.status_code == 200
    manuscript = assembly_response.json()["manuscript"]
    assert introduction["id"] in manuscript["included_section_ids"]

    export_response = client.post(f"/papers/{paper['id']}/export", json={"export_format": "markdown"})
    assert export_response.status_code == 200
    export = export_response.json()["export"]
    assert export["manuscript_id"] == manuscript["id"]
    assert export["export_format"] == "markdown"
    assert export["content"].startswith("# End To End Harness")
