import json

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.models import Paper, PromptExecutionLog
from app.models.enums import PaperType, PromptStage
from app.schemas.planning import PlanningRunCreate
from app.services.llm import LLMRequest, LLMResult
from app.services.planner import WorkflowPlanningService


class FakePlannerProvider:
    provider_name = "fake_planner"

    def generate(self, request: LLMRequest) -> LLMResult:
        payload = {
            "task_profile": {
                "document_type": "academic_paper",
                "audience": "Test reader",
                "success_criteria": ["Stay executable."],
                "constraints": ["Do not invent."],
            },
            "entry_strategy": {
                "source_mode": "new_paper",
                "current_maturity": "idea",
                "rationale": "Fake provider model path.",
            },
            "paper_plan": {
                "objective": "Exercise model-backed planner logging.",
                "global_risks": [],
                "workflow_steps": ["discover", "plan"],
            },
            "section_plans": [],
            "prompt_assembly_hints": {
                "required_prompt_modules": ["task_profile", "stage_prompt_pack"],
                "style_profile": "default_academic",
                "risk_emphasis": [],
            },
        }
        return LLMResult(
            content=json.dumps(payload),
            provider=self.provider_name,
            model="fake-model",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
                "cached_tokens": 10,
                "reasoning_tokens": 5,
                "cost_usd": 0.0123,
            },
            cost_usd=0.0123,
        )


def _create_paper(client) -> dict:
    response = client.post(
        "/papers",
        json={
            "title": "Planning Foundation",
            "paper_type": "conceptual",
            "target_language": "English",
            "target_venue": "Workshop",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_discovery_and_plan_endpoints_persist_structured_outputs(client) -> None:
    paper = _create_paper(client)

    discovery_response = client.post(
        f"/papers/{paper['id']}/discovery",
        json={
            "document_type": "academic_paper",
            "user_goal": "Write a paper about a general-purpose writing agent.",
            "audience": "Systems and HCI researchers",
            "success_criteria": [
                "Clarify the workflow architecture.",
                "Keep the plan grounded in available materials.",
            ],
            "constraints": ["Do not invent experimental results."],
            "available_source_materials": ["Repository docs", "Existing outline and draft artifacts"],
            "current_document_state": "Only product docs exist; no paper outline has been generated yet.",
            "clarifying_questions": ["Which venue template matters most?"],
            "assumptions": ["Academic paper revision is the first test case."],
            "notes": "Discovery should stay reusable beyond papers.",
            "metadata": {"source": "test"},
        },
    )

    assert discovery_response.status_code == 200
    discovery = discovery_response.json()
    assert discovery["paper_id"] == paper["id"]
    assert discovery["status"] == "active"
    assert discovery["metadata"] == {"source": "test"}

    discovery_get = client.get(f"/papers/{paper['id']}/discovery")
    assert discovery_get.status_code == 200
    assert discovery_get.json()["id"] == discovery["id"]

    plan_response = client.post(f"/papers/{paper['id']}/plan", json={})

    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["paper_id"] == paper["id"]
    assert plan["planner_mode"] == "deterministic"
    assert plan["discovery_id"] == discovery["id"]
    assert plan["task_profile"]["document_type"] == "academic_paper"
    assert plan["entry_strategy"]["source_mode"] == "new_paper"
    assert plan["entry_strategy"]["current_maturity"] == "idea"
    assert "discover" in plan["paper_plan"]["workflow_steps"]
    assert "assemble_prompts" in plan["paper_plan"]["workflow_steps"]
    assert "outline_or_outline_reconciliation" in plan["paper_plan"]["workflow_steps"]
    assert plan["section_plans"] == []
    assert "task_profile" in plan["prompt_assembly_hints"]["required_prompt_modules"]
    assert plan["prompt_assembly_hints"]["style_profile"] == "default_academic"
    assert plan["metadata"]["path"] == "deterministic"

    latest_plan = client.get(f"/papers/{paper['id']}/plan")
    assert latest_plan.status_code == 200
    assert latest_plan.json()["id"] == plan["id"]


def test_plan_uses_non_paper_document_type_profiles(client) -> None:
    paper = _create_paper(client)
    discovery_response = client.post(
        f"/papers/{paper['id']}/discovery",
        json={
            "document_type": "technical_document",
            "user_goal": "Create an implementation specification for a writing agent.",
            "audience": "Platform engineers",
        },
    )
    assert discovery_response.status_code == 200

    plan_response = client.post(f"/papers/{paper['id']}/plan", json={})

    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["task_profile"]["document_type"] == "technical_document"
    assert plan["task_profile"]["audience"] == "Platform engineers"
    assert "technical document" in plan["paper_plan"]["objective"]
    assert plan["prompt_assembly_hints"]["style_profile"] == "default_technical"
    assert any("academic paper defaults" in risk for risk in plan["paper_plan"]["global_risks"])


def test_plan_builds_mixed_section_actions_from_existing_outline_and_drafts(client) -> None:
    paper = _create_paper(client)
    outline_response = client.post(f"/papers/{paper['id']}/generate-outline", json={})
    assert outline_response.status_code == 200
    outline = outline_response.json()["outline"]
    introduction = next(node for node in outline if node["title"] == "Introduction")
    conclusion = next(node for node in outline if node["title"] == "Conclusion")

    discovery_response = client.post(
        f"/papers/{paper['id']}/discovery",
        json={
            "document_type": "academic_paper",
            "user_goal": "Revise the manuscript foundation while filling missing sections.",
            "current_document_state": "A few sections already have draft text, but many are still missing.",
        },
    )
    assert discovery_response.status_code == 200

    draft_response = client.post(
        f"/sections/{introduction['id']}/drafts",
        json={
            "kind": "section_draft",
            "version": 1,
            "content": "Existing introduction draft that should mostly be preserved.",
            "supported_evidence_ids": [],
            "status": "active",
        },
    )
    assert draft_response.status_code == 201

    plan_response = client.post(f"/papers/{paper['id']}/plan", json={})
    assert plan_response.status_code == 200
    plan = plan_response.json()

    assert plan["entry_strategy"]["source_mode"] == "mixed"
    assert plan["entry_strategy"]["current_maturity"] == "partial_draft"

    section_plans = {item["section_title"]: item for item in plan["section_plans"]}
    assert section_plans["Introduction"]["action"] == "preserve"
    assert section_plans["Conclusion"]["action"] == "draft"
    assert section_plans["Conclusion"]["section_id"] == conclusion["id"]


def test_model_backed_planner_persists_prompt_execution_log() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        paper = Paper(title="Model Planner Logging", paper_type=PaperType.CONCEPTUAL)
        session.add(paper)
        session.commit()
        session.refresh(paper)

        service = WorkflowPlanningService(session, llm_provider=FakePlannerProvider())
        plan = service.generate_plan(paper.id, PlanningRunCreate(force_deterministic=False))

        assert plan.planner_mode == "model"
        log = session.exec(
            select(PromptExecutionLog).where(
                PromptExecutionLog.paper_id == paper.id,
                PromptExecutionLog.stage == PromptStage.PLANNER,
            )
        ).first()
        assert log is not None
        assert log.provider == "fake_planner"
        assert log.model_name == "fake-model"
        assert log.status == "completed"
        assert log.prompt_hash
        assert log.prompt_tokens == 100
        assert log.completion_tokens == 40
        assert log.total_tokens == 140
        assert log.cached_tokens == 10
        assert log.reasoning_tokens == 5
        assert log.cost_usd == 0.0123
        assert log.usage_json["total_tokens"] == 140
        assert "Build a structured workflow plan" in (log.user_prompt or "")
        assert "task_profile" in (log.response_text or "")
