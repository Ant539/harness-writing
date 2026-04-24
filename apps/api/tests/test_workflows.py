def _create_paper(client) -> dict:
    response = client.post(
        "/papers",
        json={
            "title": "Unified Workflow Runner",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_workflow_runner_executes_discovery_plan_outline_and_contract_prep(client) -> None:
    paper = _create_paper(client)

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True},
    )

    assert response.status_code == 201
    payload = response.json()
    run = payload["workflow_run"]
    plan = payload["plan"]
    discovery = payload["discovery"]

    assert run["status"] == "completed"
    assert discovery["paper_id"] == paper["id"]
    assert discovery["notes"].startswith("Auto-inferred by the workflow runner")
    assert plan["entry_strategy"]["source_mode"] == "new_paper"
    assert plan["entry_strategy"]["current_maturity"] == "outline"
    assert plan["section_plans"]

    step_types = [step["step_type"] for step in run["steps"]]
    assert "discover" in step_types
    assert "plan" in step_types
    assert "generate_outline" in step_types
    assert "replan" in step_types
    assert "generate_contract" in step_types
    assert "section_action" in step_types

    outline_response = client.get(f"/papers/{paper['id']}/outline")
    assert outline_response.status_code == 200
    outline_nodes = outline_response.json()["nodes"]
    assert len(outline_nodes) >= 6

    sections_response = client.get(f"/papers/{paper['id']}/sections")
    assert sections_response.status_code == 200
    sections = sections_response.json()
    for section in sections:
        contract_response = client.get(f"/sections/{section['id']}/contract")
        assert contract_response.status_code == 200
        assert contract_response.json()["section_id"] == section["id"]

    run_detail = client.get(f"/workflow-runs/{run['id']}")
    assert run_detail.status_code == 200
    assert run_detail.json()["id"] == run["id"]


def test_workflow_runner_dry_run_persists_pending_execution_steps(client) -> None:
    paper = _create_paper(client)

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"dry_run": True, "auto_execute": True},
    )

    assert response.status_code == 201
    payload = response.json()
    run = payload["workflow_run"]

    assert run["status"] == "completed"

    step_by_type = {}
    for step in run["steps"]:
        step_by_type.setdefault(step["step_type"], []).append(step)

    assert step_by_type["discover"][0]["status"] == "completed"
    assert step_by_type["plan"][0]["status"] == "completed"
    assert step_by_type["generate_outline"][0]["status"] == "pending"

    outline_response = client.get(f"/papers/{paper['id']}/outline")
    assert outline_response.status_code == 200
    assert outline_response.json()["nodes"] == []

    list_response = client.get(f"/papers/{paper['id']}/workflow-runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run["id"]
