"""Read-only role-type, group-type, and group endpoints."""

from typing import Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import Connection
from pydantic import BaseModel

from database import get_connection
from authorization import AuthorizationService, get_authorization_service
from models.reference_data import (
    Group,
    GroupDetail,
    GroupPage,
    GroupType,
    GroupTypeDetail,
    GroupTypePage,
    RoleType,
    RoleTypeDetail,
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
    authorization: AuthorizationService = Depends(get_authorization_service),
) -> RoleTypePage:
    authorization.require("reference-data:view")
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


@router.get(
    "/role-types/{role_type_id}", response_model=RoleTypeDetail, tags=["role types"]
)
def get_role_type(
    role_type_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
    authorization: AuthorizationService = Depends(get_authorization_service),
) -> RoleTypeDetail:
    authorization.require("reference-data:view")
    return _record_by_id(
        connection,
        record_id=role_type_id,
        table="role_types",
        columns="id, name, description, created_at, modified_at",
        model=RoleTypeDetail,
        not_found_detail="Role type not found",
    )


@router.get("/group-types", response_model=GroupTypePage, tags=["group types"])
def get_group_types(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    connection: Connection[Any] = Depends(get_connection),
    authorization: AuthorizationService = Depends(get_authorization_service),
) -> GroupTypePage:
    authorization.require("reference-data:view")
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
    "/group-types/{group_type_id}",
    response_model=GroupTypeDetail,
    tags=["group types"],
)
def get_group_type(
    group_type_id: UUID,
    connection: Connection[Any] = Depends(get_connection),
    authorization: AuthorizationService = Depends(get_authorization_service),
) -> GroupTypeDetail:
    authorization.require("reference-data:view")
    return _record_by_id(
        connection,
        record_id=group_type_id,
        table="group_types",
        columns="id, name, description, created_at, modified_at",
        model=GroupTypeDetail,
        not_found_detail="Group type not found",
    )


@router.get("/groups", response_model=GroupPage, tags=["groups"])
def get_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> GroupPage:
    offset = (page - 1) * page_size
    where_clause = ""
    parameters: list[Any] = []
    scope = authorization.scope("group:view")
    if not scope.unrestricted:
        where_clause = "WHERE g.id = ANY(%s)"
        parameters.append(list(scope.ids))
    total = connection.execute(
        f"SELECT count(*) AS total FROM groups g {where_clause}", parameters
    ).fetchone()["total"]
    rows = connection.execute(
        f"""
        SELECT
          g.id,
          g.group_type_id,
          gt.name AS group_type_name,
          g.name,
          g.description,
          g.parent_id,
          parent.name AS parent_name
        FROM groups g
        JOIN group_types gt ON gt.id = g.group_type_id
        LEFT JOIN groups parent ON parent.id = g.parent_id
        {where_clause}
        ORDER BY g.name, g.id
        LIMIT %s OFFSET %s
        """,
        (*parameters, page_size, offset),
    ).fetchall()
    items = [Group.model_validate(row) for row in rows]
    return GroupPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/groups/{group_id}", response_model=GroupDetail, tags=["groups"])
def get_group(
    group_id: UUID,
    authorization: AuthorizationService = Depends(get_authorization_service),
    connection: Connection[Any] = Depends(get_connection),
) -> GroupDetail:
    row = connection.execute(
        """
        SELECT
          g.id,
          g.group_type_id,
          gt.name AS group_type_name,
          g.name,
          g.description,
          g.parent_id,
          parent.name AS parent_name,
          g.created_at,
          g.modified_at
        FROM groups g
        JOIN group_types gt ON gt.id = g.group_type_id
        LEFT JOIN groups parent ON parent.id = g.parent_id
        WHERE g.id = %s
        """,
        (group_id,),
    ).fetchone()
    if row is None or (
        not authorization.allows("group:view", group_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    return GroupDetail.model_validate(row)
