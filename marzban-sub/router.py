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

    username = sub.username
    clean = re.sub(r"[^\w]", "", username.lower()) # noqa
    hash_str = str(int(md5(username.encode()).hexdigest(), 16) % 10000).zfill(4)
    username = f"{clean}_{hash_str}"[:32]

    if iscoroutinefunction(crud.get_user):  # noqa
        # if marzneshin be completely asynchronous, use `await` to get the result
        db_user = await crud.get_user(db, username)  # noqa
    else:
        db_user = crud.get_user(db, username)  # noqa

    user: UserResponse = UserResponse.model_validate(db_user)  # noqa

    crud.update_user_sub(db, db_user, user_agent)  # noqa

    subscription_settings = SubscriptionSettings.model_validate(  # noqa
        db.query(Settings.subscription).first()[0]  # noqa
    )

    if (
            subscription_settings.template_on_acceptance
            and "text/html" in request.headers.get("Accept", [])
    ):
        return HTMLResponse(
            generate_subscription_template(db_user, subscription_settings)
        )

    response_headers = {
        "content-disposition": f'attachment; filename="{user.username}"',
        "profile-web-page-url": str(request.url),
        "support-url": subscription_settings.support_link,
        "profile-title": encode_title(subscription_settings.profile_title),
        "profile-update-interval": str(subscription_settings.update_interval),
        "subscription-userinfo": "; ".join(
            f"{key}={val}"
            for key, val in get_subscription_user_info(user).items()  # noqa
        ),
    }

    for rule in subscription_settings.rules:
        if re.match(rule.pattern, user_agent):
            if rule.result.value == "template":
                return HTMLResponse(
                    generate_subscription_template(
                        db_user, subscription_settings
                    )
                )
            elif rule.result.value == "block":
                raise HTTPException(404)
            elif rule.result.value == "base64-links":
                b64 = True
                config_format = "links"
            else:
                b64 = False
                config_format = rule.result.value

            conf = generate_subscription( # noqa
                user=db_user,
                config_format=config_format,
                as_base64=b64,
                use_placeholder=not user.is_active
                                and subscription_settings.placeholder_if_disabled,
                placeholder_remark=subscription_settings.placeholder_remark,
                shuffle=subscription_settings.shuffle_configs,
            )
            return Response(
                content=conf,
                media_type=config_mimetype[rule.result],
                headers=response_headers,
            )