from fastapi import APIRouter
from crud.users import search_users_by_username, get_user, add_user_avatar
from dependencies.deps import SessionDep, UserTokenDep
from schemas.chat import UpdateUserAvatar
from schemas.user import FindUsersByUsername, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/search-users", response_model=list[UserResponse])
async def search_users(user: FindUsersByUsername, session: SessionDep) -> list[UserResponse]:
    """
    Search users list by username
    """
    return await search_users_by_username(session=session, username=user.username)


@router.post("/get-user-data", response_model=UserResponse)
async def get_user_data(session: SessionDep, decoded_access_token: UserTokenDep) -> UserResponse:
    """
    Get user data by jwt token
    """
    user_id = decoded_access_token["user_id"]
    return await get_user(session=session, user_id=user_id)


@router.post("/update-user-avatar")
async def update_user_avatar(update_avatar: UpdateUserAvatar, session: SessionDep):
    """
    Upload new user avatar
    """
    return await add_user_avatar(session=session, update_avatar=update_avatar)