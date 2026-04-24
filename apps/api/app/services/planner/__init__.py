"""Planner service package."""

from app.services.planner.contract_generator import ContractGenerator
from app.services.planner.outline_generator import OutlineGenerator
from app.services.planner.workflow_planning import WorkflowPlanningService


class PlannerService:
    """Facade for deterministic planner behavior used before LLM integration."""

    outline_generator = OutlineGenerator
    contract_generator = ContractGenerator
    workflow_planning_service = WorkflowPlanningService


__all__ = [
    "ContractGenerator",
    "OutlineGenerator",
    "PlannerService",
    "WorkflowPlanningService",
]
