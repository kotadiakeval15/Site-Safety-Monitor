"""Pagination primitives shared by services and routes."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageParams:
    """Normalized pagination request parameters."""

    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


@dataclass
class Page(Generic[T]):
    """A page of results plus the metadata needed to build pagination meta."""

    items: list[T]
    total_items: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return ceil(self.total_items / self.page_size)


def paginate(items: list[T], total_items: int, params: PageParams) -> Page[T]:
    """Wrap raw results into a :class:`Page`."""

    return Page(
        items=items,
        total_items=total_items,
        page=params.page,
        page_size=params.page_size,
    )
