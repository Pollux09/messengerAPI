from fastapi import APIRouter, HTTPException
from crud.users import (
    add_user_avatar,
    get_user,
    get_users_list,
    search_users as search_users_crud,
    update_profile,
    update_username,
)
from dependencies.deps import SessionDep, UserTokenDep
from schemas.chat import UpdateUserAvatar
from schemas.user import SearchUsersRequest, UpdateProfile, UpdateUsername, UserId, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/search-users", response_model=list[UserResponse])
async def search_users_handler(
    data: SearchUsersRequest,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> list[UserResponse]:
    """
    Search users list by username or nickname
    """
    return await search_users_crud(
        session=session,
        query=data.query,
        current_user_id=decoded_access_token["user_id"],
    )


@router.post("/get-user-data", response_model=UserResponse)
async def get_user_data(session: SessionDep, decoded_access_token: UserTokenDep) -> UserResponse:
    """
    Get user data by jwt token
    """
    user_id = decoded_access_token["user_id"]
    return await get_user(session=session, user_id=user_id)


@router.post("/get-user-profile", response_model=UserResponse)
async def get_user_profile(
    data: UserId,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> UserResponse:
    return await get_user(session=session, user_id=data.user_id)


@router.post("/get-all-users", response_model=list[UserResponse])
async def get_all_users(
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> list[UserResponse]:
    current_user = await get_user(
        session=session,
        user_id=decoded_access_token["user_id"],
    )
    return await get_users_list(
        session=session,
        current_user_id=decoded_access_token["user_id"],
        exclude_current_user=not current_user.is_admin,
    )


@router.post("/get-employees", response_model=list[UserResponse])
async def get_employees(
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> list[UserResponse]:
    return await get_users_list(
        session=session,
        current_user_id=decoded_access_token["user_id"],
        admins_only=True,
    )


@router.post("/update-user-avatar")
async def update_user_avatar(
    update_avatar: UpdateUserAvatar,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    """
    Upload new user avatar
    """
    if decoded_access_token["user_id"] != update_avatar.user_id:
        raise HTTPException(status_code=403, detail="You can update only your own avatar")
    return await add_user_avatar(session=session, update_avatar=update_avatar)


@router.post("/update-username", response_model=UserResponse)
async def update_current_username(
    data: UpdateUsername,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> UserResponse:
    return await update_username(
        session=session,
        current_user_id=decoded_access_token["user_id"],
        data=data,
    )


@router.post("/update-profile", response_model=UserResponse)
async def update_current_profile(
    data: UpdateProfile,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> UserResponse:
    return await update_profile(
        session=session,
        current_user_id=decoded_access_token["user_id"],
        data=data,
    )
