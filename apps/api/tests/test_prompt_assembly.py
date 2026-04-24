def _create_paper(client) -> dict:
    response = client.post(
        "/papers",
        json={
            "title": "Prompt Assembly Foundation",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_prompt_assembly_endpoint_builds_and_persists_writer_prompt(client) -> None:
    paper = _create_paper(client)
    discovery = client.post(
        f"/papers/{paper['id']}/discovery",
        json={
            "document_type": "academic_paper",
            "user_goal": "Draft a paper about a unified writing agent.",
            "audience": "Systems researchers",
            "success_criteria": ["Stay grounded.", "Keep the workflow reusable."],
            "constraints": ["Do not invent results."],
        },
    ).json()
    plan = client.post(f"/papers/{paper['id']}/plan", json={}).json()

    style = client.post(
        f"/papers/{paper['id']}/style-guide",
        json={
            "tone": "precise academic",
            "voice": "clear",
            "citation_style": "APA",
            "terminology_preferences": {"agent": "writing agent"},
            "forbidden_patterns": ["Do not use hype language."],
            "format_rules": {},
        },
    ).json()
    assert style["tone"] == "precise academic"

    response = client.post(
        f"/papers/{paper['id']}/prompt-assemblies",
        json={
            "stage": "writer",
            "planning_run_id": plan["id"],
            "additional_instructions": "Focus on the paper-level writer setup.",
        },
    )

    assert response.status_code == 201
    artifact = response.json()
    assert artifact["paper_id"] == paper["id"]
    assert artifact["planning_run_id"] == plan["id"]
    assert artifact["stage"] == "writer"
    assert artifact["version"] == 1
    assert "task_profile" in artifact["module_keys"]
    assert "stage_prompt_pack" in artifact["module_keys"]
    assert "style_guidance" in artifact["module_keys"]
    assert any(module["title"] == "Stage Instructions" for module in artifact["modules"])
    assert any(module["title"] == "Stage Prompt Pack" for module in artifact["modules"])
    assert "Paper Harness is not only an academic-paper workflow" in artifact["system_prompt"]
    assert "Prompt pack version: v1" in artifact["system_prompt"]
    assert "Action policy:" in artifact["system_prompt"]
    assert "Tone: precise academic" in artifact["system_prompt"]
    assert artifact["prompt_hash"]
    assert artifact["prompt_pack_version"] == "v1"
    assert artifact["metadata"]["prompt_pack"]["version"] == "v1"
    assert "Use the assembled modules and this runtime context" in artifact["user_prompt"]
    assert "Focus on the paper-level writer setup." in artifact["user_prompt"]

    latest = client.get(f"/prompt-assemblies/{artifact['id']}")
    assert latest.status_code == 200
    assert latest.json()["id"] == artifact["id"]

    listing = client.get(f"/papers/{paper['id']}/prompt-assemblies?stage=writer")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == artifact["id"]
    logs = client.get(f"/papers/{paper['id']}/prompt-logs?stage=writer")
    assert logs.status_code == 200
    assert logs.json()[0]["prompt_assembly_id"] == artifact["id"]
    assert logs.json()[0]["prompt_hash"] == artifact["prompt_hash"]
    assert logs.json()[0]["prompt_pack_version"] == "v1"
    assert discovery["id"] == client.get(f"/papers/{paper['id']}/discovery").json()["id"]


def test_prompt_assembly_versions_supersede_prior_stage_artifacts(client) -> None:
    paper = _create_paper(client)
    client.post(f"/papers/{paper['id']}/discovery", json={"document_type": "academic_paper"})
    client.post(f"/papers/{paper['id']}/plan", json={})

    first = client.post(
        f"/papers/{paper['id']}/prompt-assemblies",
        json={"stage": "reviewer"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/papers/{paper['id']}/prompt-assemblies",
        json={"stage": "reviewer"},
    )
    assert second.status_code == 201
    assert second.json()["version"] == 2
    assert second.json()["status"] == "active"

    items = client.get(f"/papers/{paper['id']}/prompt-assemblies?stage=reviewer").json()
    assert items[0]["version"] == 2
    assert items[0]["status"] == "active"
    assert items[1]["version"] == 1
    assert items[1]["status"] == "superseded"


def test_prompt_assembly_has_stage_prompt_packs_for_all_agent_roles(client) -> None:
    paper = _create_paper(client)
    client.post(f"/papers/{paper['id']}/discovery", json={"document_type": "academic_paper"})
    client.post(f"/papers/{paper['id']}/plan", json={})

    expected_roles = {
        "planner": "Planning layer",
        "writer": "Section writer",
        "reviewer": "Section reviewer",
        "reviser": "Revision writer",
        "verifier": "Grounding verifier",
        "editor": "Global editor",
    }
    for stage, role in expected_roles.items():
        response = client.post(
            f"/papers/{paper['id']}/prompt-assemblies",
            json={"stage": stage},
        )
        assert response.status_code == 201
        artifact = response.json()
        pack_module = next(
            module for module in artifact["modules"] if module["key"] == "stage_prompt_pack"
        )
        assert artifact["metadata"]["prompt_pack"]["role"] == role
        assert f"Stage role: {role}" in pack_module["content"]
        assert "Required inputs:" in pack_module["content"]
        assert "Output contract:" in pack_module["content"]
