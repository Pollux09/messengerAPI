from pydantic import BaseModel, Field


class StoredCryptKeys(BaseModel):
    public_key: str = Field(default="")
    encrypted_private_key: str = Field(default="")
    kdf_salt: str = Field(default="")
    encryption_nonce: str = Field(default="")


class SignUpRequest(BaseModel):
    email: str
    password: str
    username: str
    nickname: str = Field(min_length=1, max_length=64)
    crypt_keys: StoredCryptKeys


class LoginSuccessResponse(BaseModel):
    access_token: str
    refresh_token: str
    crypt_keys: StoredCryptKeys


class EmailScheme(BaseModel):
    email: str


class VerifyEmailScheme(BaseModel):
    email: str
    code: str


class LoginData(BaseModel):
    email: str
    password: str


class AccessToken(BaseModel):
    access_token: str


class RefreshToken(BaseModel):
    refresh_token: str


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str


class RegistrationPendingResponse(BaseModel):
    message: str
