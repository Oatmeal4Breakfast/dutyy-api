from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_current_user, get_project_service
from src.domain.dutyy import Dutyy, DutyyStatus
from src.domain.project import Project, ProjectStatus, PublishingStatus
from src.domain.user import UserSummary
from src.service.project_service import (
    EditDutyyCommand,
    EditProjectCommand,
    ProjectService,
)


class CreateProjectRequest(BaseModel):
    name: str


class EditProjectRequest(BaseModel):
    name: str | None = None
    status: ProjectStatus | None = None

    @property
    def is_empty(self) -> bool:
        return self.name is None and self.status is None


class CreateDutyyRequest(BaseModel):
    title: str
    details: str | None = None


class EditDutyyRequest(BaseModel):
    title: str | None = None
    status: DutyyStatus | None = None
    details: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.title is None and self.status is None and self.details is None


class DutyyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    details: str | None
    status: DutyyStatus
    project_id: UUID
    created_date: datetime
    modified_date: datetime | None
    completed_date: datetime | None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    status: ProjectStatus
    publishing_status: PublishingStatus
    created_date: datetime
    modified_date: datetime | None
    published_date: datetime | None
    completed_date: datetime | None
    dutyys: list[DutyyResponse]


router = APIRouter(prefix="/dutyy/api/v1", tags=["Projects", "Dutyy"])

ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
CurrentUser = Annotated[UserSummary, Depends(get_current_user)]


@router.post(
    "/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED
)
async def create_project(
    payload: CreateProjectRequest, user: CurrentUser, service: ProjectServiceDep
):
    project: Project = await service.create_project_draft(
        project_name=payload.name,
        owner_id=user.id,
    )
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(user: CurrentUser, service: ProjectServiceDep):
    projects: list[Project] = await service.list_projects(owner_id=user.id)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project_by_id(
    project_id: UUID, user: CurrentUser, service: ProjectServiceDep
):
    return ProjectResponse.model_validate(
        await service.get_project(project_id=project_id, owner_id=user.id)
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: UUID,
    user: CurrentUser,
    service: ProjectServiceDep,
    payload: EditProjectRequest,
):
    if payload.is_empty:
        raise HTTPException(status_code=400, detail="no fields provided to update")

    command = EditProjectCommand(**payload.model_dump())
    project: Project = await service.edit_project(
        owner_id=user.id, project_id=project_id, updates=command
    )

    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/publish", status_code=status.HTTP_204_NO_CONTENT)
async def publish_project(
    project_id: UUID, user: CurrentUser, service: ProjectServiceDep
):
    await service.publish_project(project_id=project_id, owner_id=user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/unpublish", response_model=ProjectResponse)
async def unpublish_project(
    project_id: UUID, user: CurrentUser, service: ProjectServiceDep
):
    return ProjectResponse.model_validate(
        await service.unpublish_project(project_id=project_id, owner_id=user.id)
    )


@router.post(
    "/projects/{project_id}/dutyys",
    response_model=DutyyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dutyy(
    user: CurrentUser,
    service: ProjectServiceDep,
    project_id: UUID,
    payload: CreateDutyyRequest,
):
    dutyy: Dutyy = await service.add_dutyy(
        dutyy_title=payload.title,
        details=payload.details,
        project_id=project_id,
        owner_id=user.id,
    )
    return DutyyResponse.model_validate(dutyy)


@router.delete(
    "/projects/{project_id}/dutyys/{dutyy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dutyy(
    user: CurrentUser, service: ProjectServiceDep, project_id: UUID, dutyy_id: UUID
):
    await service.remove_dutyy(
        dutyy_id=dutyy_id, project_id=project_id, owner_id=user.id
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/dutyys/{dutyy_id}", response_model=DutyyResponse)
async def patch_dutyy(
    dutyy_id: UUID,
    payload: EditDutyyRequest,
    service: ProjectServiceDep,
    user: CurrentUser,
):
    if payload.is_empty:
        raise HTTPException(status_code=400, detail="no fields provided to update")
    command = EditDutyyCommand(**payload.model_dump())
    dutyy: Dutyy = await service.edit_dutyy(
        dutyy_id=dutyy_id, owner_id=user.id, updates=command
    )

    return DutyyResponse.model_validate(dutyy)
