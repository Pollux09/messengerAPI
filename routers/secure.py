from fastapi import APIRouter, HTTPException
from crud.crypto_keys import add_crypto_keys
from dependencies.deps import SessionDep, UserTokenDep
from schemas.auth import UploadCryptKeys

router = APIRouter(prefix="/secure", tags=["secure"])

@router.post("/upload-keys")
async def upload_keys(session: SessionDep, keys: UploadCryptKeys, decoded_access_token: UserTokenDep):
    try:
        await add_crypto_keys(session=session, keys=keys, user_id=decoded_access_token["user_id"])
        return {'status': True, 'action': 'upload keys'}
    except Exception as e:
        raise HTTPException(status_code=408, detail=str(e))
    