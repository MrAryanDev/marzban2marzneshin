from datetime import datetime, timezone
from enum import Enum
from hashlib import md5
from os import system
from re import sub
from secrets import token_hex
from time import time
from uuid import UUID

import pytz
from decouple import RepositoryEnv, Config
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import marzban_models as m
import marzneshin_models as msh

NO_INBOUND_GUIDE_URL = ""

# Marzban Config
marzban_repository = RepositoryEnv('/opt/marzban/.env')
marzban_config = Config(marzban_repository)

marzneshin_repository = RepositoryEnv('/etc/opt/marzneshin/.env')
marzneshin_config = Config(marzneshin_repository)

marzban_sqlalchemy_url = marzban_config('SQLALCHEMY_DATABASE_URL', default="sqlite:///db.sqlite3")
marzneshin_sqlalchemy_url = marzneshin_config('SQLALCHEMY_DATABASE_URL', default="sqlite:///db.sqlite3")

if marzban_sqlalchemy_url.startswith("sqlite"):
    marzban_sqlalchemy_url = f"sqlite:////var/lib/marzban/{marzban_sqlalchemy_url.split('/')[-1]}"

if marzneshin_sqlalchemy_url.startswith("sqlite"):
    marzneshin_sqlalchemy_url = f"sqlite:////var/lib/marzneshin/{marzneshin_sqlalchemy_url.split('/')[-1]}"

marzban_session = Session(
    bind=create_engine(marzban_sqlalchemy_url)
)

marzneshin_session = Session(
    bind=create_engine(marzneshin_sqlalchemy_url)
)


class AuthAlgorithm(Enum):
    PLAIN = "plain"
    XXH128 = "xxh128"


marzneshin_auth_algoritem = marzneshin_config(
    "AUTH_GENERATION_ALGORITHM",
    cast=AuthAlgorithm,
    default=AuthAlgorithm.XXH128
)

marzban_subscription_url_prefix = marzban_config("XRAY_SUBSCRIPTION_URL_PREFIX", default="").strip("/")

# remove to free the memory
del marzban_repository, marzneshin_repository, \
    marzban_config, marzneshin_config, marzban_sqlalchemy_url, marzneshin_sqlalchemy_url

console = Console(style="yellow")


def main():
    system("clear")

    accept_settings = console.input("I Can Just Handle Vless Or Vmess Proxy Types; Do You Accept? (y/n): ")
    if accept_settings.lower() != "y":
        console.print("Exiting...")
        return

    if marzneshin_auth_algoritem != AuthAlgorithm.PLAIN:
        console.print("Using the XXH128 Hashing algorithm makes your Marzban users unable to stay connected."
                      " [yellow] Set Env AUTH_GENERATION_ALGORITHM=plain[/]",
                      style="bold orange_red1")

    inbound = marzneshin_session.query(msh.Inbound).first()
    if not inbound:
        console.print(f"No Inbound Found In Marzneshin Database, Create A Inbound First", style="bold red")
        return

    start_time = time()

    admins_service = dict()
    admins_id = dict()
    admin_users_count = dict()

    marzban_admins = marzban_session.query(m.Admin).all()
    marzban_admin_count = len(marzban_admins)

    console.print(f"You Have {marzban_admin_count} Admin In Marzban Database", style="bold")

    admin_progress = Progress(expand=True)
    with admin_progress as progress_:
        for m_admin in progress_.track(marzban_admins, description="Write Marzban Admins To Marzneshin"):
            service = msh.Service(
                name=m_admin.username + token_hex(2),
                inbounds=[inbound],  # noqa: ignore
                users=[]  # noqa: ignore
            )
            try:
                marzneshin_session.add(service)
                marzneshin_session.commit()
            except IntegrityError:
                # rollback and get service
                marzneshin_session.rollback()
                service = marzneshin_session.query(msh.Service).filter_by(name=service.name).first()
            else:
                marzneshin_session.refresh(service)
            try:
                msh_admin = msh.Admin(
                    username=m_admin.username,  # noqa: ignore
                    hashed_password=m_admin.hashed_password,  # noqa: ignore
                    is_sudo=m_admin.is_sudo,  # noqa: ignore
                    enabled=True,
                    all_services_access=False,
                    modify_users_access=True,
                    subscription_url_prefix=marzban_subscription_url_prefix,
                    services=[service]  # noqa: ignore
                )
                marzneshin_session.add(msh_admin)

                marzneshin_session.commit()
            except IntegrityError:
                marzneshin_session.rollback()

                admin_db = marzneshin_session.query(msh.Admin).filter_by(username=m_admin.username).first()
                if admin_db.is_sudo:
                    continue

                admin_db.hashed_password = m_admin.hashed_password
                admin_db.services = [service]
                admins_service[admin_db.id] = service
                admins_id[m_admin.id] = admin_db.id

                marzneshin_session.commit()
            else:
                marzneshin_session.refresh(msh_admin)

                admins_service[msh_admin.id] = service
                admins_id[m_admin.id] = msh_admin.id

            admin_users_count[m_admin.id] = {"username": m_admin.username, "users_count": 0}

    del marzban_admins, admin_progress
    if marzban_admin_count > 0:
        del m_admin, msh_admin
    else:
        console.print("No Admin Found In Marzban Database, Exiting...")
        return

    console.print("Marzban Admins Written To Marzneshin Database\n\n", style="bold")

    marzban_users = marzban_session.query(m.User).all()
    marzban_user_count = len(marzban_users)

    tehran_tz = pytz.timezone("Asia/Tehran")

    console.print(f"You Have {marzban_user_count} User In Marzban Database", style="bold")

    user_progress = Progress(expand=True)
    with (user_progress as progress_):
        for m_user in progress_.track(marzban_users, description="Write Marzban Users To Marzneshin"):
            if m_user.admin_id not in admins_id:
                continue



            admin_id = admins_id[m_user.admin_id]

            clean = sub(r"\W", "", m_user.username.lower())
            hash_str = str(int(md5(m_user.username.encode()).hexdigest(), 16) % 10000).zfill(4)
            username = f"{clean}_{hash_str}"[:32]

            expire_date = (
                datetime.fromtimestamp(m_user.expire, tz=timezone.utc)  # noqa: ignore
                .astimezone(tehran_tz)
                if m_user.expire
                else None
            )

            user_proxy = marzban_session.query(
                m.Proxy
            ).filter(
                m.Proxy.user_id == m_user.id,
                m.Proxy.type.in_((m.ProxyTypes.VLESS, m.ProxyTypes.VMess))
            ).first()

            if not user_proxy:
                console.print(f"Can't Add User {m_user.username} To Marzneshin, No (vless|vmess)Proxy Found",
                              style="bold red")
                continue

            user_uuid = user_proxy.settings.get("id")
            if not user_uuid:
                console.print(f"Can't Add User {m_user.username} To Marzneshin, No Proxy UUID Found",
                              style="bold red")
                continue

            user_key = UUID(user_uuid).hex

            admin_users_count[m_user.admin_id]["users_count"] += 1
            msh_user = msh.User(
                username=username,
                key=user_key,
                expire_strategy=(
                    msh.UserExpireStrategy.START_ON_FIRST_USE if m_user.status == m.UserStatus.on_hold else
                    msh.UserExpireStrategy.FIXED_DATE if m_user.expire else msh.UserExpireStrategy.NEVER
                ),
                expire_date=expire_date,
                usage_duration=m_user.on_hold_expire_duration if m_user.status == m.UserStatus.on_hold else None,
                activation_deadline=(
                    m_user.on_hold_timeout
                    if m_user.status == m.UserStatus.on_hold and m_user.on_hold_timeout
                    else None
                ),
                services=[admins_service[admin_id]],  # noqa: ignore
                data_limit=m_user.data_limit,
                admin_id=admin_id,
                data_limit_reset_strategy=msh.UserDataUsageResetStrategy(m_user.data_limit_reset_strategy.value),
                note=m_user.note,
                used_traffic=m_user.used_traffic if m_user.used_traffic <= (m_user.data_limit or m_user.used_traffic
                                                                            + 1) else m_user.data_limit,
                lifetime_used_traffic=m_user.lifetime_used_traffic,
                sub_updated_at=m_user.sub_updated_at,
                sub_revoked_at=m_user.sub_revoked_at,
                created_at=m_user.created_at,
                online_at=m_user.online_at,
                edit_at=m_user.edit_at
            )

            marzneshin_session.add(msh_user)
            try:
                marzneshin_session.commit()
            except IntegrityError:
                marzneshin_session.rollback()
                continue

    console.print("Marzban Users Written To Marzneshin Database\n\n", style="bold")

    end_time = time()

    result_table = Table(title="Marzban Info Writen To Marzneshin", header_style="bold", expand=True)

    result_table.add_column("Admin")
    result_table.add_column("Users Count")
    for admin_info in admin_users_count.values():
        result_table.add_row(admin_info["username"], str(admin_info["users_count"]))  # noqa: ignore

    result_table.add_section()
    result_table.add_row("Time Spent", str(round(end_time - start_time, 2)) + " s")

    console.print(result_table)

    console.print("Please [cyan]Restart The Marzneshin[/] Panel", style="bold yellow")


def test():
    # Delete association table entries
    marzneshin_session.execute(msh.users_services.delete())
    marzneshin_session.execute(msh.inbounds_services.delete())
    marzneshin_session.execute(msh.admins_services.delete())

    # Delete User entities
    marzneshin_session.query(msh.User).delete()

    # Delete Service entities
    marzneshin_session.query(msh.Service).delete()

    # Delete Admin entities
    marzneshin_session.query(msh.Admin).delete()

    # Commit the changes
    marzneshin_session.commit()

    print("All relevant data has been deleted from the Marzneshin database.")
if __name__ == '__main__':
    main()
    # test()