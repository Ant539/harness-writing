from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from app import models  # noqa: F401


def test_database_schema_contains_core_tables() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "discovery_records",
        "papers",
        "planning_runs",
        "prompt_assembly_artifacts",
        "prompt_execution_logs",
        "outline_nodes",
        "section_contracts",
        "evidence_items",
        "evidence_packs",
        "draft_units",
        "review_comments",
        "revision_tasks",
        "section_approvals",
        "source_materials",
        "style_guides",
        "user_interactions",
        "clarification_requests",
        "workflow_checkpoints",
        "workflow_runs",
        "workflow_step_runs",
    }.issubset(table_names)
