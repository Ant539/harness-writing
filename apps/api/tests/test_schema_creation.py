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
        "outline_nodes",
        "section_contracts",
        "evidence_items",
        "evidence_packs",
        "draft_units",
        "review_comments",
        "revision_tasks",
        "source_materials",
        "style_guides",
        "workflow_runs",
        "workflow_step_runs",
    }.issubset(table_names)
