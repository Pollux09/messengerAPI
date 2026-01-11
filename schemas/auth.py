from pydantic import BaseModel

class UploadCryptKeys(BaseModel):
    public_key: str
    private_key: str


class LoginSuccessResponse(BaseModel):
    access_token: str
    refresh_token: str
    crypt_keys: UploadCryptKeys


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