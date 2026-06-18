from fastapi import APIRouter, HTTPException
from crud.crypto_keys import upsert_crypto_keys
from dependencies.deps import SessionDep, UserTokenDep
from schemas.auth import StoredCryptKeys

router = APIRouter(prefix="/secure", tags=["secure"])

@router.post("/upload-keys")
async def upload_keys(session: SessionDep, keys: StoredCryptKeys, decoded_access_token: UserTokenDep):
    try:
        await upsert_crypto_keys(
            session=session,
            keys=keys,
            user_id=decoded_access_token["user_id"],
        )
        await session.commit()
        return {'status': True, 'action': 'upload keys'}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=408, detail=str(e))
    
