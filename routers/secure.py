import base64
from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from schemas import UploadCryptKeys
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import logging
from crud import add_crypto_keys
from utils.jwtUtil import jwtUtil, verify_user_middleware
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

secureRouter = APIRouter()

@secureRouter.post("/upload-key")
async def upload_key(keys: UploadCryptKeys, decoded_access_token = Depends(verify_user_middleware), db: Session = Depends(get_db)):
    try:
        await add_crypto_keys(db=db, keys=keys, user_id=decoded_access_token["user_id"])
    except Exception as e:
        raise HTTPException(status_code=408, detail=str(e))
    