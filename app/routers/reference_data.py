"""Read-only role-type, group-type, and group endpoints."""

from typing import Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection
from pydantic import BaseModel

from database import get_connection
from models.reference_data import (
    Group,
    GroupPage,
    GroupType,
    GroupTypePage,
    RoleType,
    RoleTypePage,
)


router = APIRouter()
ModelType = TypeVar("ModelType", bound=BaseModel)


def _page_rows(
    connection: Connection[Any],
    *,
    table: str,
    columns: str,
    order_by: str,
    page: int,
    page_size: int,
    model: type[ModelType],
) -> tuple[list[ModelType], int]:
    offset = (page - 1) * page_size
    total = connection.execute(f"SELECT count(*) AS total FROM {table}").fetchone()[
        "total"
    ]
    rows = connection.execute(
        f"SELECT {columns} FROM {table} ORDER BY {order_by} LIMIT %s OFFSET %s",
        (page_size, offset),
    ).fetchall()
    return [model.model_validate(row) for row in rows], total


def _record_by_id(
    connection: Connection[Any],
    *,
    record_id: UUID,
    table: str,
    columns: str,
    model: type[ModelType],
    not_found_detail: str,
) -> ModelType:
    row = connection.execute(
        f"SELECT {columns} FROM {table} WHERE id = %s", (record_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=not_found_detail,
        )
    return model.model_validate(row)


@router.get("/role-types", response_model=RoleTypePage, tags=["role types"])
def get_role_types(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
) -> RoleTypePage:
    items, total = _page_rows(
        connection,
        table="role_types",
        columns="id, name, description",
        order_by="name, id",
        page=page,
        page_size=page_size,
        model=RoleType,
    )
    return RoleTypePage(items=items, page=page, page_size=page_size, total=total)


@router.get("/role-types/{role_type_id}", response_model=RoleType, tags=["role types"])
def get_role_type(
    role_type_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
) -> RoleType:
    return _record_by_id(
        connection,
        record_id=role_type_id,
        table="role_types",
        columns="id, name, description",
        model=RoleType,
        not_found_detail="Role type not found",
    )


@router.get("/group-types", response_model=GroupTypePage, tags=["group types"])
def get_group_types(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
) -> GroupTypePage:
    items, total = _page_rows(
        connection,
        table="group_types",
        columns="id, name, description",
        order_by="name, id",
        page=page,
        page_size=page_size,
        model=GroupType,
    )
    return GroupTypePage(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/group-types/{group_type_id}", response_model=GroupType, tags=["group types"]
)
def get_group_type(
    group_type_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
) -> GroupType:
    return _record_by_id(
        connection,
        record_id=group_type_id,
        table="group_types",
        columns="id, name, description",
        model=GroupType,
        not_found_detail="Group type not found",
    )


@router.get("/groups", response_model=GroupPage, tags=["groups"])
def get_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
) -> GroupPage:
    items, total = _page_rows(
        connection,
        table="groups",
        columns="id, group_type_id, name, description, parent_id",
        order_by="name, id",
        page=page,
        page_size=page_size,
        model=Group,
    )
    return GroupPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/groups/{group_id}", response_model=Group, tags=["groups"])
def get_group(
    group_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
) -> Group:
    return _record_by_id(
        connection,
        record_id=group_id,
        table="groups",
        columns="id, group_type_id, name, description, parent_id",
        model=Group,
        not_found_detail="Group not found",
    )
