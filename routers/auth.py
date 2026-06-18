from fastapi import APIRouter, HTTPException, BackgroundTasks
from crud.crypto_keys import get_user_crypto_keys
from crud.users import (
    check_user_exists,
    create_user,
    ensure_user_is_approved,
    get_user_by_id,
    login_user,
)
from dependencies.deps import SessionDep, EmailDep
from models.user import User
from schemas.auth import (
    AuthTokens,
    EmailScheme,
    LoginData,
    LoginSuccessResponse,
    RefreshToken,
    RegistrationPendingResponse,
    SignUpRequest,
    StoredCryptKeys,
    VerifyEmailScheme,
)
from utils.jwt_util import jwt_util

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.post("/sign-up", response_model=RegistrationPendingResponse)
async def sign_up(
    user: SignUpRequest,
    session: SessionDep,
    background_task: BackgroundTasks,
    email_service: EmailDep,
) -> RegistrationPendingResponse:
    """
    Sign up user and create pending registration request
    """
    new_user: User = await create_user(session=session, user=user)
    background_task.add_task(
        email_service.send_registration_pending_email,
        new_user.email,
        new_user.nickname,
    )
    return RegistrationPendingResponse(
        message="Регистрация принята. Ожидайте подтверждения администратора, уведомление придет на почту",
    )


@router.post("/sign-in", response_model=LoginSuccessResponse)
async def login(login_data: LoginData, session: SessionDep) -> LoginSuccessResponse:
    """
    Sign in user and return jwt tokens and crypt keys
    """
    user = await login_user(session=session, login_data=login_data)

    access_token, refresh_token = await jwt_util.create_jwt_tokens(user=user)
    crypt_keys = await get_user_crypto_keys(session=session, user_id=user.id)

    return LoginSuccessResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        crypt_keys=StoredCryptKeys(
            public_key=crypt_keys.public_key,
            encrypted_private_key=crypt_keys.encrypted_private_key,
            kdf_salt=crypt_keys.kdf_salt,
            encryption_nonce=crypt_keys.encryption_nonce,
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
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    # send email background task
    background_task.add_task(email_service.send_email, data.email)

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
    decoded = await jwt_util.decode_jwt_token(
        token=token.refresh_token,
        required_type="refresh",
    )

    user_id = decoded["user_id"]
    user = await get_user_by_id(session=session, user_id=user_id)
    await ensure_user_is_approved(user)
    access_token, refresh_token = await jwt_util.create_jwt_tokens(user=user)
    return AuthTokens(access_token=access_token, refresh_token=refresh_token)
