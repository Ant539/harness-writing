from app.models import PlanningRun
from app.services.planner import WorkflowPlanningService


def _create_paper(client) -> dict:
    response = client.post(
        "/papers",
        json={
            "title": "Agent State",
            "paper_type": "conceptual",
            "target_language": "English",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_discovery_clarification_loop_persists_questions_answers_and_interactions(client) -> None:
    paper = _create_paper(client)
    discovery = client.post(
        f"/papers/{paper['id']}/discovery",
        json={
            "document_type": "academic_paper",
            "clarifying_questions": ["Which venue should this target?"],
        },
    ).json()

    created = client.post(f"/papers/{paper['id']}/discovery/clarifications", json={})

    assert created.status_code == 200
    clarification = created.json()[0]
    assert clarification["discovery_id"] == discovery["id"]
    assert clarification["question"] == "Which venue should this target?"
    assert clarification["status"] == "pending"

    answer = client.post(
        f"/clarifications/{clarification['id']}/answer",
        json={"answer": "Target the systems workshop track."},
    )

    assert answer.status_code == 200
    answered = answer.json()
    assert answered["status"] == "answered"
    assert answered["answer"] == "Target the systems workshop track."
    assert answered["response_interaction_id"]

    interactions = client.get(f"/papers/{paper['id']}/interactions")
    assert interactions.status_code == 200
    messages = [(item["role"], item["message"]) for item in interactions.json()]
    assert ("assistant", "Which venue should this target?") in messages
    assert ("user", "Target the systems workshop track.") in messages

    latest_discovery = client.get(f"/papers/{paper['id']}/discovery").json()
    answers = latest_discovery["metadata"]["clarification_answers"]
    assert answers[0]["question"] == "Which venue should this target?"
    assert answers[0]["answer"] == "Target the systems workshop track."


def test_workflow_runner_pauses_on_blocked_section_and_creates_checkpoint(client) -> None:
    paper = _create_paper(client)
    section = client.post(
        f"/papers/{paper['id']}/sections",
        json={"title": "Unsupported Section", "level": 1, "order_index": 1},
    )
    assert section.status_code == 201

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True},
    )

    assert response.status_code == 201
    run = response.json()["workflow_run"]
    assert run["status"] == "waiting_for_user"
    assert run["metadata"]["waiting_for_user"] is True
    assert run["metadata"]["checkpoint_type"] == "blocked_section"
    assert run["current_step_key"].startswith("checkpoint:")

    checkpoints = client.get(f"/papers/{paper['id']}/workflow-checkpoints")
    assert checkpoints.status_code == 200
    checkpoint = checkpoints.json()[0]
    assert checkpoint["workflow_run_id"] == run["id"]
    assert checkpoint["checkpoint_type"] == "blocked_section"
    assert checkpoint["status"] == "pending"
    assert "Unsupported Section" in checkpoint["metadata"]["section_title"]

    detail = client.get(f"/workflow-runs/{run['id']}").json()
    blocked_steps = [
        step
        for step in detail["steps"]
        if step["step_type"] == "section_action" and step["status"] == "skipped"
    ]
    assert blocked_steps

    still_pending = client.post(f"/workflow-runs/{run['id']}/resume", json={})
    assert still_pending.status_code == 409


def test_workflow_resume_after_resolved_checkpoint_replans_and_continues(client) -> None:
    paper = _create_paper(client)
    section = client.post(
        f"/papers/{paper['id']}/sections",
        json={"title": "Unsupported Section", "level": 1, "order_index": 1},
    ).json()

    paused = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True},
    ).json()["workflow_run"]
    checkpoint = client.get(f"/papers/{paper['id']}/workflow-checkpoints").json()[0]

    evidence = client.post(
        f"/papers/{paper['id']}/evidence",
        json={
            "section_id": section["id"],
            "source_type": "note",
            "content": "New source material makes the section draftable after resume.",
            "confidence": 0.9,
            "metadata": {},
        },
    )
    assert evidence.status_code == 201
    resolved = client.post(
        f"/workflow-checkpoints/{checkpoint['id']}/resolve",
        json={"resolution_note": "Evidence added for the blocked section."},
    )
    assert resolved.status_code == 200

    resumed = client.post(
        f"/workflow-runs/{paused['id']}/resume",
        json={"force_replan": True, "auto_execute": True},
    )

    assert resumed.status_code == 200
    run = resumed.json()["workflow_run"]
    assert run["status"] == "completed"
    assert run["metadata"]["waiting_for_user"] is False
    assert "replan" in [step["step_type"] for step in run["steps"]]

    current = client.get(f"/sections/{section['id']}/drafts/current")
    assert current.status_code == 200
    assert current.json()["section_id"] == section["id"]


def test_workflow_step_retry_appends_retry_step(client) -> None:
    paper = _create_paper(client)
    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True, "section_limit": 1},
    )
    assert response.status_code == 201
    run = response.json()["workflow_run"]
    assemble_step = next(step for step in run["steps"] if step["step_type"] == "assemble_prompts")

    retry = client.post(
        f"/workflow-steps/{assemble_step['id']}/retry",
        json={"force_replan": False},
    )

    assert retry.status_code == 200
    payload = retry.json()
    assert payload["workflow_run"]["status"] == "completed"
    assert payload["retried_step"]["step_key"] == "retry:assemble_prompts"
    assert payload["retried_step"]["status"] == "completed"
    assert payload["retried_step"]["result"]["retried"] is True


def test_workflow_runner_pauses_on_unknown_plan_and_creates_clarification(
    client,
    monkeypatch,
) -> None:
    def fake_generate_plan(self, paper_id, payload):
        plan = PlanningRun(
            paper_id=paper_id,
            discovery_id=payload.discovery_id,
            task_profile_json={
                "document_type": "unknown",
                "audience": "Unknown",
                "success_criteria": [],
                "constraints": [],
            },
            entry_strategy_json={
                "source_mode": "unknown",
                "current_maturity": "idea",
                "rationale": "Need user clarification before choosing an entry path.",
            },
            paper_plan_json={
                "objective": "Wait for clarification.",
                "global_risks": ["Entry path is unclear."],
                "workflow_steps": ["discover", "plan"],
            },
            section_plans_json=[],
            prompt_assembly_hints_json={
                "required_prompt_modules": ["task_profile"],
                "style_profile": "default_structured",
                "risk_emphasis": [],
            },
        )
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(plan)
        return plan

    monkeypatch.setattr(WorkflowPlanningService, "generate_plan", fake_generate_plan)
    paper = _create_paper(client)

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True},
    )

    assert response.status_code == 201
    run = response.json()["workflow_run"]
    assert run["status"] == "waiting_for_user"
    assert run["metadata"]["checkpoint_type"] == "unknown_plan"

    clarifications = client.get(f"/papers/{paper['id']}/clarifications")
    assert clarifications.status_code == 200
    assert clarifications.json()
    assert clarifications.json()[0]["workflow_run_id"] == run["id"]

    checkpoints = client.get(f"/papers/{paper['id']}/workflow-checkpoints")
    assert checkpoints.status_code == 200
    assert checkpoints.json()[0]["checkpoint_type"] == "unknown_plan"
    assert checkpoints.json()[0]["clarification_request_ids"]
