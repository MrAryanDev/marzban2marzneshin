from typing import Annotated

from fastapi import APIRouter, Request, Header, Depends  # noqa
from pydantic import BaseModel  # noqa
from sqlalchemy.orm import Session, DeclarativeBase

crud = type("", (), {})

router = APIRouter()
DBDep = Annotated[Session, Depends()]
UserResponse = type("UserResponse", (BaseModel,), {})
SubscriptionSettings = type("SubscriptionSettings", (BaseModel,), {})
Settings = type("Settings", (DeclarativeBase,), {})
config_mimetype = {}


def generate_subscription_template(*_, **__):
    pass


def encode_title(*_, **__):
    pass


def get_subscription_user_info(*_, **__):
    pass


def generate_subscription(*_, **__):
    pass

def user_subscription(db_user: object, request: Request, db: DBDep, user_agent: str = Header(default="")):
    pass

### MARZBAN SUBSCRIPTIONS ###
@router.get("/{token}/")
@router.get("/{token}", include_in_schema=False)
async def upsert_user(
        token: str,
        request: Request,
        db: DBDep,
        user_agent: str = Header(default=""),
):
    import re

    from base64 import b64decode, b64encode
    from datetime import datetime
    from hashlib import sha256, md5
    from typing import Union, List
    from inspect import iscoroutinefunction

    from pydantic import BaseModel # noqa
    import jwt # noqa
    from fastapi import HTTPException, Response # noqa
    from fastapi.responses import HTMLResponse # noqa

    class MarzbanToken(BaseModel):
        username: str
        created_at: datetime | str

    marzban_jwt_tokens: List[str] = {{ marzban_jwt_tokens }}  # noqa

    def get_subscription_payload(
            token: str, # noqa
    ) -> Union[MarzbanToken, None]:
        try:
            if len(token) < 15:
                return None

            if token.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."):
                for marzban_jwt_token in marzban_jwt_tokens:
                    try:
                        payload = jwt.decode(token, marzban_jwt_token, algorithms=["HS256"])
                    except jwt.InvalidSignatureError:
                        continue

                    if payload.get("access") == "subscription":
                        return MarzbanToken(
                            username=payload["sub"],
                            created_at=datetime.utcfromtimestamp(payload["iat"]),  # noqa
                        )
                    else:
                        return None
            else:
                u_token, u_signature = token[:-10], token[-10:]
                try:
                    u_token_dec = b64decode(
                        u_token.encode("utf-8")
                        + b"=" * (-len(u_token.encode("utf-8")) % 4),
                        altchars=b"-_",
                        validate=True,
                    ).decode("utf-8")
                except Exception as e:
                    print(e)
                    return None

                for marzban_jwt_token in marzban_jwt_tokens:
                    u_token_resign = b64encode(
                        sha256((u_token + marzban_jwt_token).encode("utf-8")).digest(),
                        altchars=b"-_",
                    ).decode("utf-8")[:10]

                    if u_signature == u_token_resign:
                        u_username, u_created_at = u_token_dec.split(",")
                        return MarzbanToken(
                            username=u_username,
                            created_at=datetime.utcfromtimestamp(int(u_created_at)),  # noqa
                        )
                return None
        except jwt.PyJWTError:
            return None

    sub = get_subscription_payload(token=token)
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid subscription token")

    username = re.sub(r"\W", "", sub.username.lower())

    async def get_user(u: str):
        if iscoroutinefunction(crud.get_user):  # noqa
            # if marzneshin be completely asynchronous, use `await` to get the result
            db_user = await crud.get_user(db, u)  # noqa
        else:
            db_user = crud.get_user(db, u)  # noqa
        return db_user

    def username_hash(user_username: str) -> str:
        '''
        Generate a hash for the username
        '''
        return str(int(md5(user_username.encode()).hexdigest(), 16) % 10000).zfill(4)

    async def get_user_with_change_name(
            user_username: str, exists_checker
    ):
        '''
        Generate a username by appending a hash to the original username
        '''
        base_username = user_username
        if user := await exists_checker(base_username):
            return user
        sep = "_"
        hash_str = username_hash(base_username)
        while True:
            user_username = f"{user_username}{sep}{hash_str}"
            if len(user_username) >= 32:
                sep = ""
                user_username = f"{base_username}{sep}{hash_str}"
                if len(user_username) >= 32:
                    return None
            if user := await exists_checker(user_username):
                return user
            hash_str = username_hash(user_username)

    db_user = await get_user_with_change_name(username, get_user)

    if db_user is None:
        raise HTTPException(status_code=400, detail="Invalid subscription token")

    if iscoroutinefunction(user_subscription):  # noqa
        # if marzneshin be completely asynchronous, use `await` to get the result
        return await user_subscription(db_user, request, db, user_agent)  # noqa
    else:
        return user_subscription(db_user, request, db, user_agent)  # noqa

