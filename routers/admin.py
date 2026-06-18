from fastapi import APIRouter, BackgroundTasks
from crud.users import (
    REGISTRATION_APPROVED,
    REGISTRATION_REJECTED,
    create_role,
    delete_unapproved_user,
    get_all_roles,
    get_pending_users,
    get_user,
    build_user_response,
    update_user_registration_status,
    update_user_role,
)
from dependencies.deps import AdminUserDep, EmailDep, SessionDep
from schemas.user import RegistrationDecision, RoleCreate, RoleResponse, RoleUpdate, UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/pending-users", response_model=list[UserResponse])
async def get_pending_registrations(
    session: SessionDep,
    admin_user: AdminUserDep,
) -> list[UserResponse]:
    return await get_pending_users(session)


@router.post("/approve-user", response_model=UserResponse)
async def approve_user_registration(
    data: RegistrationDecision,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    email_service: EmailDep,
    admin_user: AdminUserDep,
) -> UserResponse:
    user = await update_user_registration_status(
        session,
        data,
        new_status=REGISTRATION_APPROVED,
    )
    background_tasks.add_task(
        email_service.send_registration_decision_email,
        user.email,
        user.nickname,
        True,
        None,
    )
    return await get_user(session, user.id)


@router.post("/reject-user", response_model=UserResponse)
async def reject_user_registration(
    data: RegistrationDecision,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    email_service: EmailDep,
    admin_user: AdminUserDep,
) -> UserResponse:
    user = await update_user_registration_status(
        session,
        data,
        new_status=REGISTRATION_REJECTED,
    )
    response = await build_user_response(session, user)
    background_tasks.add_task(
        email_service.send_registration_decision_email,
        user.email,
        user.nickname,
        False,
        user.rejection_reason,
    )
    await delete_unapproved_user(session, user)
    return response


@router.post("/roles", response_model=list[RoleResponse])
async def list_roles(
    session: SessionDep,
    admin_user: AdminUserDep,
) -> list[RoleResponse]:
    return await get_all_roles(session)


@router.post("/create-role", response_model=RoleResponse)
async def create_role_handler(
    data: RoleCreate,
    session: SessionDep,
    admin_user: AdminUserDep,
) -> RoleResponse:
    return await create_role(session, data)


@router.post("/update-user-role/{user_id}", response_model=UserResponse)
async def update_user_role_handler(
    user_id: str,
    data: RoleUpdate,
    session: SessionDep,
    admin_user: AdminUserDep,
) -> UserResponse:
    return await update_user_role(session, user_id, data)
