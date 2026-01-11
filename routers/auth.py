from fastapi import APIRouter, HTTPException, BackgroundTasks
from crud.crypto_keys import get_user_crypto_keys
from crud.users import create_user, login_user, check_user_exists, get_user
from dependencies.deps import SessionDep, EmailDep
from models.User import User
from schemas.auth import LoginData, LoginSuccessResponse, UploadCryptKeys, EmailScheme, VerifyEmailScheme, RefreshToken, \
    AuthTokens
from schemas.user import UserCreate
from utils.jwt_util import jwtUtil

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.post("/sign-up", response_model=AuthTokens)
async def sign_up(user: UserCreate, session: SessionDep) -> AuthTokens:
    """
    Sign up user and return jwt tokens
    """
    new_user: User = await create_user(session=session, user=user)
    access_token, refresh_token = await jwtUtil.create_jwt_tokens(user=new_user)
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)


@router.post("/sign-in", response_model=LoginSuccessResponse)
async def login(login_data: LoginData, session: SessionDep) -> LoginSuccessResponse:
    """
    Sign in user and return jwt tokens and crypt keys
    """
    user = await login_user(session=session, login_data=login_data)
    if not user:
        raise HTTPException(detail="login data is invalid", status_code=401)

    tokens = await jwtUtil.createJwtTokens(user=user)
    crypt_keys = await get_user_crypto_keys(session=session, user_id=user.id)

    return LoginSuccessResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        crypt_keys=UploadCryptKeys(
            public_key=crypt_keys.public_key,
            private_key=crypt_keys.private_key,
        )
    )


@router.post("/send-verify-code")
async def send_verify_code(
        data: EmailScheme,
        session: SessionDep,
        background_task: BackgroundTasks,
        email_service: EmailDep
) -> dict[str, bool | str]:
    """
    Send verify code to email
    """
    user = await check_user_exists(session=session, email=data.email)
    if user:
        raise HTTPException(status_code=409, detail="This email already taken")

    # send email background task
    background_task.add_task(await email_service.send_email(to_send_email=data.email))

    return {'status': True, 'action': 'send verify code'}


@router.post("/verify-email-code")
async def verify_email_code(verify: VerifyEmailScheme, email_service: EmailDep) -> bool:
    """
    Verify email code
    """
    return await email_service.verify_email_code(user_email=verify.email, user_code=verify.code)


@router.post("/refresh-tokens", response_model=AuthTokens)
async def refresh_tokens(token: RefreshToken, session: SessionDep) -> AuthTokens:
    """
    Refresh jwt tokens
    """
    decoded = await jwtUtil.decode_jwt_token(token=token.refresh_token)

    user_id = decoded["user_id"]
    user = await get_user(session=session, user_id=user_id)
    access_token, refresh_token = await jwtUtil.create_jwt_tokens(user=user)
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)