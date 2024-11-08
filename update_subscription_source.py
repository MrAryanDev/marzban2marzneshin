from base64 import b64encode

import docker

marzban_sub_router = """
### MARZBAN SUBSCRIPTIONS ###
@router.get("/{token}/")
@router.get("/{token}", include_in_schema=False)
async def upsert_user(
        token: str,
        request: Request,
        db: DBDep,
        user_agent: str = Header(default=""),
):
    from base64 import b64decode, b64encode
    from datetime import datetime
    from hashlib import sha256
    from typing import Union
    from pydantic import BaseModel
    import jwt
    from hashlib import md5
    from inspect import iscoroutinefunction

    marzban_jwt_token = "{{ marzban_jwt_token }}"

    class MarzbanToken(BaseModel):
        username: str
        created_at: datetime | str

    def get_subscription_payload(
            token: str,
    ) -> Union[MarzbanToken, None]:
        try:
            if len(token) < 15:
                return None

            if token.startswith("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."):
                payload = jwt.decode(token, marzban_jwt_token, algorithms=["HS256"])
                if payload.get("access") == "subscription":
                    return MarzbanToken(
                        username=payload["sub"],
                        created_at=datetime.utcfromtimestamp(payload["iat"]),
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

                u_token_resign = b64encode(
                    sha256((u_token + marzban_jwt_token).encode("utf-8")).digest(),
                    altchars=b"-_",
                ).decode("utf-8")[:10]

                if u_signature == u_token_resign:
                    u_username, u_created_at = u_token_dec.split(",")
                    return MarzbanToken(
                        username=u_username,
                        created_at=datetime.utcfromtimestamp(int(u_created_at)),
                    )
                else:
                    print(u_signature, "...", u_token_resign)
                    return None
        except jwt.PyJWTError:
            return None

    sub = get_subscription_payload(token=token)
    if not sub:
        raise HTTPException(status_code=400, detail="Invalid subscription token")

    username = sub.username
    clean = re.sub(r"[^\w]", "", username.lower())
    hash_str = str(int(md5(username.encode()).hexdigest(), 16) % 10000).zfill(4)
    username = f"{clean}_{hash_str}"[:32]

    if iscoroutinefunction(crud.get_user):
        # if marzneshin be completely asynchronous, use `await` to get the result
        db_user = await crud.get_user(db, username)
    else:
        db_user = crud.get_user(db, username)

    user: UserResponse = UserResponse.model_validate(db_user)

    crud.update_user_sub(db, db_user, user_agent)

    subscription_settings = SubscriptionSettings.model_validate(
        db.query(Settings.subscription).first()[0]
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
            for key, val in get_subscription_user_info(user).items()
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

            conf = generate_subscription(
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
"""

# Initialize Docker client
client = docker.from_env()

# Docker compose file path
docker_compose_path = "/etc/opt/marzneshin/docker-compose.yml"

# Find the marzneshin service container
marzneshin_container = None
for container in client.containers.list():
    if 'marzneshin-marzneshin' in container.name:
        marzneshin_container = container
        break

if not marzneshin_container:
    print("Marzneshin container not found.")
    exit(1)

# Path to the subscription.py file inside the container
subscription_file_path = "app/routes/subscription.py"

# Check if the file exists and update it if necessary
exec_result = marzneshin_container.exec_run(f"cat {subscription_file_path}")
if exec_result.exit_code != 0:
    print(f"Error: Unable to read {subscription_file_path}")
    exit(1)

file_content = exec_result.output.decode('utf-8')

if "### MARZBAN SUBSCRIPTIONS ###" not in file_content:
    print("Adding Marzban subscriptions code to subscription.py")

    # Encode the content to base64 to avoid issues with special characters
    encoded_content = b64encode(marzban_sub_router.encode()).decode()

    # Create a temporary file with the content
    temp_file = "/tmp/marzban_sub_router.txt"
    create_temp_file = f"echo {encoded_content} | base64 -d > {temp_file}"
    exec_result = marzneshin_container.exec_run(f'/bin/sh -c "{create_temp_file}"')
    if exec_result.exit_code != 0:
        print(f"Error: Unable to create temporary file")
        exit(1)

    # Append the content of the temporary file to the target file
    append_command = f"cat {temp_file} >> {subscription_file_path}"
    exec_result = marzneshin_container.exec_run(f'/bin/sh -c "{append_command}"')
    if exec_result.exit_code != 0:
        print(f"Error: Unable to append content to {subscription_file_path}")
        exit(1)

    # Remove the temporary file
    remove_temp_file = f"rm {temp_file}"
    marzneshin_container.exec_run(f'/bin/sh -c "{remove_temp_file}"')


    print("subscription.py updated successfully.")
    print("Restarting Marzneshin container...")
    marzneshin_container.restart()
    print("Marzneshin container restarted successfully.")
else:
    print("Marzban subscriptions code already exists in subscription.py")