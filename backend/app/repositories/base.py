"""Generic async repository base class."""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Common data-access operations for a single model."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def add(self, entity: ModelT) -> ModelT:
        """Persist a new entity (flushed, not committed)."""

        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete an entity."""

        await self._session.delete(entity)
        await self._session.flush()

    async def count(self) -> int:
        """Return the total row count for the model."""

        result = await self._session.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())
