"""Small persistence helpers for route services."""

import uuid
from typing import Any, TypeVar

from fastapi import HTTPException
from sqlmodel import SQLModel, Session

ModelT = TypeVar("ModelT", bound=SQLModel)


def get_or_404(session: Session, model: type[ModelT], item_id: uuid.UUID, name: str) -> ModelT:
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return item


def create_item(session: Session, item: ModelT) -> ModelT:
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_item(session: Session, item: ModelT, values: dict[str, Any]) -> ModelT:
    for key, value in values.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_item(session: Session, item: SQLModel) -> None:
    session.delete(item)
    session.commit()
