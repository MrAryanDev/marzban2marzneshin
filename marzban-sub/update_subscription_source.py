from base64 import b64encode

import docker

from jinja2 import Environment

SCRIPT_NAME = "marzban2marzneshin"
SCRIPTS_DIR = "/opt/MrAryanDev"
CONFIG_DIR = f"{SCRIPTS_DIR}/.config"
SCRIPT_CONFIG_DIR = f"{CONFIG_DIR}/{SCRIPT_NAME}"
JWT_FILE_PATH = f"{SCRIPT_CONFIG_DIR}/jwt.txt"

MARZBAN_SUB_ROUTER = """\n\n\n
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

with open(JWT_FILE_PATH) as f:
    tokens = list(map(lambda x: x.strip(), f.read().splitlines()))


file_content: str = exec_result.output.decode('utf-8')

file_contents = file_content.split("### MARZBAN SUBSCRIPTIONS ###")
router_content = "\n\n".join(file_contents[1:])

continue_updating = False

if len(file_contents) > 0:
    for token in tokens:
        if token not in router_content:
            continue_updating = True
            break
else:
    continue_updating = True

if not continue_updating:
    print("Source Already Up to date.")
    exit(0)

file_content = b64encode(file_contents[0].encode()).decode()
print("Adding Marzban subscriptions code to subscription.py")


if not tokens:
    print("no jwt token in jwt tokens file.")
    exit(1)

env = Environment()
rendered_sub_router = env.from_string(MARZBAN_SUB_ROUTER).render(marzban_jwt_tokens=tokens)
# Encode the content to base64 to avoid issues with special characters
encoded_content = b64encode(rendered_sub_router.encode()).decode()

# Create a temporary file with the content
temp_file = "/tmp/marzban_sub_router.txt"
create_temp_file = f"echo {file_content + encoded_content} | base64 -d > {temp_file}"
exec_result = marzneshin_container.exec_run(f'/bin/sh -c "{create_temp_file}"')
if exec_result.exit_code != 0:
    print(f"Error: Unable to create temporary file, {exec_result.output}")
    exit(1)

# Append the content of the temporary file to the target file
append_command = f"cat {temp_file} > {subscription_file_path}"
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