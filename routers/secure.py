from fastapi import APIRouter, Depends, HTTPException

from crud.crypto_keys import add_crypto_keys
from database import get_db
from schemas import UploadCryptKeys
import logging
from utils.jwtUtil import verify_user_middleware
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

secureRouter = APIRouter()

@secureRouter.post("/upload-key")
async def upload_key(keys: UploadCryptKeys, decoded_access_token = Depends(verify_user_middleware), db: Session = Depends(get_db)):
    try:
        await add_crypto_keys(db=db, keys=keys, user_id=decoded_access_token["user_id"])
    except Exception as e:
        raise HTTPException(status_code=408, detail=str(e))
    