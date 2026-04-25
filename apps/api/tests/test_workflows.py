from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.models import DraftUnit, EvidenceItem, EvidencePack, OutlineNode, Paper, ReviewComment, RevisionTask, SectionContract
from app.models.enums import (
    ArtifactStatus,
    DraftKind,
    EvidenceSourceType,
    PaperType,
    ReviewCommentType,
    SectionAction,
    SectionStatus,
    Severity,
    WorkflowStepStatus,
)
from app.schemas.planning import SectionPlan
from app.services.section_actions import SectionActionExecutor


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
    assert "assemble_prompts" in step_types
    assert "generate_contract" in step_types
    assert "section_action" in step_types

    prompt_response = client.get(f"/papers/{paper['id']}/prompt-assemblies")
    assert prompt_response.status_code == 200
    prompt_stages = {item["stage"] for item in prompt_response.json()}
    assert prompt_stages >= {"writer", "reviewer", "reviser", "verifier", "editor"}

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


def test_workflow_runner_uses_discovery_document_type_for_outline(client) -> None:
    paper = _create_paper(client)

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={
            "auto_execute": True,
            "discovery": {
                "document_type": "report",
                "user_goal": "Prepare a decision report for operators.",
                "audience": "Operations leads",
            },
        },
    )

    assert response.status_code == 201
    plan = response.json()["plan"]
    assert plan["task_profile"]["document_type"] == "report"

    outline = client.get(f"/papers/{paper['id']}/outline").json()["nodes"]
    titles = {node["title"] for node in outline}
    assert {"Executive Summary", "Findings", "Recommendations"}.issubset(titles)


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
    assert step_by_type["assemble_prompts"][0]["status"] == "completed"
    assert step_by_type["generate_outline"][0]["status"] == "pending"

    outline_response = client.get(f"/papers/{paper['id']}/outline")
    assert outline_response.status_code == 200
    assert outline_response.json()["nodes"] == []

    list_response = client.get(f"/papers/{paper['id']}/workflow-runs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == run["id"]


def test_workflow_runner_draft_action_creates_section_draft_from_plan(client) -> None:
    paper = _create_paper(client)
    outline = client.post(f"/papers/{paper['id']}/generate-outline", json={}).json()["outline"]
    introduction = next(node for node in outline if node["title"] == "Introduction")
    evidence = client.post(
        f"/papers/{paper['id']}/evidence/upload",
        json=[
            {
                "section_id": introduction["id"],
                "source_type": "paper_summary",
                "source_ref": "workflow-note",
                "content": "Planner-driven section execution connects planning actions to drafting.",
                "citation_key": "workflow2026",
                "confidence": 0.9,
                "metadata": {},
            }
        ],
    )
    assert evidence.status_code == 201

    response = client.post(
        f"/papers/{paper['id']}/workflow-runs",
        json={"auto_execute": True, "section_limit": 1},
    )

    assert response.status_code == 201
    run = response.json()["workflow_run"]
    section_action = next(step for step in run["steps"] if step["step_type"] == "section_action")
    assert section_action["status"] == "completed"
    assert section_action["result"]["action"] == "draft"
    assert section_action["result"]["outcome"] == "draft"
    assert section_action["result"]["draft_id"]

    current = client.get(f"/sections/{introduction['id']}/drafts/current")
    assert current.status_code == 200
    assert current.json()["id"] == section_action["result"]["draft_id"]


def test_section_action_executor_preserves_polishes_rewrites_repairs_and_blocks() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        paper = Paper(title="Section Actions", paper_type=PaperType.CONCEPTUAL)
        session.add(paper)
        session.commit()
        session.refresh(paper)

        preserve = _section_with_draft(session, paper, "Preserve", SectionStatus.DRAFTED)
        polish = _section_with_draft(session, paper, "Polish", SectionStatus.DRAFTED)
        rewrite = _section_with_draft(session, paper, "Rewrite", SectionStatus.DRAFTED)
        repair = _section_with_draft(session, paper, "Repair", SectionStatus.REVISION_REQUIRED)
        blocked = _section_with_draft(session, paper, "Blocked", SectionStatus.DRAFTED)
        _add_revision_context(session, paper, repair)

        executor = SectionActionExecutor(session)

        preserved = executor.execute(
            paper=paper,
            section=preserve,
            section_plan=_plan(preserve, SectionAction.PRESERVE),
        )
        assert preserved.status == WorkflowStepStatus.COMPLETED
        assert preserved.result["outcome"] == "preserved"
        assert _active_draft(session, preserve).version == 1

        polished = executor.execute(
            paper=paper,
            section=polish,
            section_plan=_plan(polish, SectionAction.POLISH),
        )
        assert polished.status == WorkflowStepStatus.COMPLETED
        assert polished.result["execution_path"] == "conservative_fallback_revision"
        assert "Polish pass applied" in _active_draft(session, polish).content

        rewritten = executor.execute(
            paper=paper,
            section=rewrite,
            section_plan=_plan(rewrite, SectionAction.REWRITE),
        )
        assert rewritten.status == WorkflowStepStatus.COMPLETED
        assert rewritten.result["execution_path"] == "conservative_fallback_revision"
        assert "rewritten from the existing draft basis" in _active_draft(session, rewrite).content

        repaired = executor.execute(
            paper=paper,
            section=repair,
            section_plan=_plan(repair, SectionAction.REPAIR),
        )
        assert repaired.status == WorkflowStepStatus.COMPLETED
        assert repaired.result["execution_path"] == "review_revision_service"
        assert repaired.result["resolved_review_comment_ids"]

        blocked_result = executor.execute(
            paper=paper,
            section=blocked,
            section_plan=_plan(blocked, SectionAction.BLOCKED),
        )
        assert blocked_result.status == WorkflowStepStatus.SKIPPED
        assert blocked_result.result["outcome"] == "blocked"


def _section_with_draft(
    session: Session,
    paper: Paper,
    title: str,
    status: SectionStatus,
) -> OutlineNode:
    section = OutlineNode(
        paper_id=paper.id,
        title=title,
        level=1,
        goal=f"Develop {title}.",
        expected_claims=[f"{title} advances the workflow."],
        status=status,
        order_index=1,
    )
    session.add(section)
    session.commit()
    session.refresh(section)
    draft = DraftUnit(
        section_id=section.id,
        kind=DraftKind.SECTION_DRAFT,
        version=1,
        content=f"Existing {title.lower()} draft.",
        supported_evidence_ids=[],
        status=ArtifactStatus.ACTIVE,
    )
    session.add(draft)
    session.commit()
    session.refresh(section)
    return section


def _add_revision_context(session: Session, paper: Paper, section: OutlineNode) -> None:
    contract = SectionContract(
        section_id=section.id,
        purpose=f"Repair {section.title}.",
        questions_to_answer=["What needs repair?"],
        required_claims=["Repair the existing section."],
        required_evidence_count=1,
        forbidden_patterns=[],
        tone="clear academic",
    )
    evidence = EvidenceItem(
        paper_id=paper.id,
        section_id=section.id,
        source_type=EvidenceSourceType.NOTE,
        content="Repair evidence keeps the section grounded.",
        confidence=0.9,
    )
    session.add(contract)
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    pack = EvidencePack(
        section_id=section.id,
        evidence_item_ids=[str(evidence.id)],
        coverage_summary="Repair evidence pack.",
        open_questions=[],
        status=ArtifactStatus.ACTIVE,
    )
    draft = _active_draft(session, section)
    comment = ReviewComment(
        target_draft_id=draft.id,
        comment_type=ReviewCommentType.LOGIC_GAP,
        severity=Severity.MEDIUM,
        comment="Repair needs clearer support.",
        suggested_action="Add evidence-grounded repair text.",
        resolved=False,
    )
    task = RevisionTask(
        section_id=section.id,
        draft_id=draft.id,
        task_description="Resolve the repair context.",
        priority=Severity.MEDIUM,
        status=ArtifactStatus.ACTIVE,
    )
    session.add(pack)
    session.add(comment)
    session.add(task)
    session.commit()


def _plan(section: OutlineNode, action: SectionAction) -> SectionPlan:
    return SectionPlan(
        section_id=section.id,
        section_title=section.title,
        action=action,
        reason=f"Test planner selected {action.value}.",
        needs_evidence=action in {SectionAction.DRAFT, SectionAction.REPAIR, SectionAction.REWRITE},
        needs_review_loop=action in {SectionAction.DRAFT, SectionAction.REPAIR, SectionAction.REWRITE, SectionAction.POLISH},
    )


def _active_draft(session: Session, section: OutlineNode) -> DraftUnit:
    draft = session.exec(
        select(DraftUnit).where(
            DraftUnit.section_id == section.id,
            DraftUnit.status == ArtifactStatus.ACTIVE,
        )
    ).first()
    assert draft is not None
    return draft
