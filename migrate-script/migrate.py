from datetime import datetime, timezone as datetime_timezone
from hashlib import md5
from os import mkdir
from os.path import exists
from re import sub
from sqlite3 import connect, Error
from sys import exit as sys_exit
from typing import Optional, Sequence
from uuid import UUID

from httpx import stream, HTTPError
from psutil import virtual_memory

from decouple import RepositoryEnv
from pytz import timezone
from rich import get_console
from rich.progress import Progress
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from yaml import safe_load

# script info
__author__ = "MrAryanDev"
SCRIPT_NAME = "marzban2marzneshin"
GITHUB_REPOSITORY = f"https://github.com/MrAryanDev/{SCRIPT_NAME}"
TELEGRAM_CHANNEL = "https://t.me/MrAryanDevChan"
SCRIPT_COLOR_NAME = "[bold][blue]Marzban[/][/] [yellow]->[/] [bold][red]Marzneshin[/][/]"

# script config
console = get_console()
console.style = "bold"
DEFAULT_MARZBAN_DATAS_DB_PATH = f"/root/{SCRIPT_NAME}.db"
SCRIPTS_DIR = "/opt/MrAryanDev"
CONFIG_DIR = f"{SCRIPTS_DIR}/.config"
SCRIPT_CONFIG_DIR = f"{CONFIG_DIR}/{SCRIPT_NAME}"
SCRIPT_DIR = f"{SCRIPTS_DIR}/{SCRIPT_NAME}"
JWT_FILE_PATH = f"{SCRIPT_CONFIG_DIR}/jwt.txt"
SOURCE_UPDATER_FILE = "https://raw.githubusercontent.com/MrAryanDev/marzban2marzneshin/refs/heads/master/marzban-sub/update_subscription_source.py"
PYTHON_EXECUTABLE = f"{SCRIPTS_DIR}/.venv/bin/python"
SOURCE_UPDATER_FILE_PATH = f"{SCRIPT_DIR}/update_subscription_source.py"
SOURCE_UPDATER_SYSTEMD_PATH = f"/etc/systemd/system/{SCRIPT_NAME}.service"
SOURCE_UPDATER_LOG_PATH = f"{SCRIPT_DIR}/log.txt"
SOURCE_UPDATER_SYSTEMD_CONTENT = f"""[Unit]
Description={SCRIPT_NAME} Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={SCRIPT_DIR}
ExecStart={PYTHON_EXECUTABLE} "{SOURCE_UPDATER_FILE_PATH}"
Restart=always
RestartSec=3600
StandardOutput=append:{SOURCE_UPDATER_LOG_PATH}
StandardError=append:{SOURCE_UPDATER_LOG_PATH}

[Install]
WantedBy=multi-user.target"""

# marzban settings
MARZBAN_ENV_FILE = "/opt/marzban/.env"

MARZBAN_DOCKER_FILE = "/opt/marzban/docker-compose.yml"
MARZBAN_DOCKER_FILE_ENV_PATH = [
    "services",
    "marzban",
    "environment"
]
MARZBAN_SUBSCRIPTIONS_URL_PREFIX_KEY = "XRAY_SUBSCRIPTION_URL_PREFIX"
MARZBAN_DEFAULT_SUBSCRIPTION_URL_PREFIX = ""
MARZBAN_SQLALCHEMY_URL_KEY = "SQLALCHEMY_DATABASE_URL"
MARZBAN_DEFAULT_SQLALCHEMY_URL = "sqlite:////var/lib/marzban/db.sqlite3"

# marzneshin settings
MARZNESHIN_SQLALCHEMY_URL_KEY = "SQLALCHEMY_DATABASE_URL"
MARZNESHIN_DOCKER_FILE = "/etc/opt/marzneshin/docker-compose.yml"
MARZNESHIN_DOCKER_FILE_ENV_PATH = [
    "services",
    "marzneshin",
    "environment"
]
MARZNESHIN_ENV_FILE = "/etc/opt/marzneshin/.env"
MARZNESHIN_DEFAULT_SQLALCHEMY_URL = "sqlite:////var/lib/marzneshin/db.sqlite3"
MARZNESHIN_AUTH_GENERATION_ALGORITHM_KEY = "AUTH_GENERATION_ALGORITHM"
MARZNESHIN_DEFAULT_AUTH_GENERATION_ALGORITHM = "xxh128"


def clear_console() -> None:
    console.clear(home=False)


def error(message: str, do_exit: bool = True) -> None:
    console.print(f"[red]Error[/][white]:[/] [yellow]{message}[/]")
    if do_exit:
        sys_exit(1)


def warning(message: str) -> None:
    console.print(f"[#ffa500]Warning[/][white]:[/] [yellow]{message}[/]")


def info(message: str) -> None:
    console.print(f"[green]Info[/][white]:[/] [yellow]{message}[/]")


def get_input(message: str) -> str:
    return console.input(f"[blue]>[/] [yellow]{message}[/][white]?[/] ")


def panel() -> None:
    while True:
        clear_console()

        # script name
        console.print(f"{SCRIPT_NAME}\n")

        # developer info
        console.print(f"Author: [blue]{__author__}[/]\n")
        console.print(f"GitHub Repository: [blue]{GITHUB_REPOSITORY}[/]\n")
        console.print(f"Telegram Channel: [blue]{TELEGRAM_CHANNEL}[/]\n\n")

        # select the option
        # export marzban data
        # import data to marzneshin
        # exit
        console.print(f"1. Export Marzban Data")
        console.print(f"2. Import Data To Marzneshin")
        console.print(f"3. Exit")
        option = get_input("Select an option")
        if option == "1":
            export_marzban_data()
        elif option == "2":
            import_marzban_data()
        elif option == "3":
            console.print("[bold][green]Bye![/][/]")
            sys_exit(0)
        else:
            error("Invalid Choice.", do_exit=False)


def check_marzban_requirements() -> None:
    if not exists(MARZBAN_ENV_FILE):
        error("Marzban Config(.env) not found. Please Install The Marzban.")

    if not exists(MARZBAN_DOCKER_FILE):
        error("Marzban Docker-Compose(.yml) not found. Please Install The Marzban.")


def check_marzneshin_requirements() -> None:
    if not exists(MARZNESHIN_ENV_FILE):
        error("Marzneshin Config(.env) not found. Please Install The Marzneshin.")

    if not exists(MARZNESHIN_DOCKER_FILE):
        error("Marzneshin Docker-Compose(.yml) not found. Please Install The Marzneshin.")


def get_marzban_transform_protocol() -> str:
    warning("It is only possible to transfer users who were using the [u]vless[/] or [u]vmess[/] protocol in Marzban.")
    while True:
        vless_or_vmess = get_input("Which protocol should be the priority for transmission(vless/vmess)").lower()
        if vless_or_vmess in ("vless", "vmess"):
            return vless_or_vmess
        error("Invalid Choice.", do_exit=False)


def check_sqlite_file(file_path: str) -> bool:
    try:
        conn = connect(file_path)
        conn.close()
        return True
    except Error:  # sqlite3.Error
        return False


def get_marzneshin_datas_db_path() -> str:
    while True:
        db_path = get_input(
            f"Please enter the database path of marzban datas(get from first option)\[default={DEFAULT_MARZBAN_DATAS_DB_PATH}]")
        db_path = db_path or DEFAULT_MARZBAN_DATAS_DB_PATH
        # check if the path is valid
        if check_sqlite_file(db_path):
            return db_path
        else:
            error("Invalid Path. Try again.", do_exit=False)


def dealing_with_existing_users() -> str:
    warning(
        "It is possible that one or more users already exist during the adding users phase."
        "\nrename: Add some characters to end of username."
        "\nupdate: update the current user info[save username]."
        "\nskip: Nothing is done."
    )
    while True:
        deal = get_input("How to dealing with existing users(rename/update/skip)")
        if deal in ("rename", "update", "skip"):
            return deal
        else:
            error("Invalid choice. Try again", do_exit=False)


def dealing_with_non_uuid_users() -> str:
    warning(
        "It is possible that one or more users have not any VLESS/VMESS uuid in database during the adding users phase."
        "\nrevoke: Generate new uuid fot that user."
        "\nskip: Nothing is done."
    )
    while True:
        deal = get_input("How to dealing with non-uuid users(revoke/skip)")
        if deal in ("revoke", "skip"):
            return deal
        else:
            error("Invalid choice. Try again", do_exit=False)


def dealing_with_existing_admin() -> str:
    warning(
        f"It is possible that one or more admins already exist during the adding admins phase."
        f"\nrename: Add some digits to end of username."
        f"\nupdate: Update the current admin info[save username](Non-sudo admins)."
        f"\nskip: Nothing is done."
    )
    while True:
        deal = get_input("How to dealing with admins(rename/update/skip)")
        if deal in ("rename", "update", "skip"):
            return deal
        else:
            error("Invalid choice. Try again", do_exit=False)


def chunk_size() -> int:
    unused_memory = virtual_memory().available * (1024 ** 2)  # unused memory as bytes

    return unused_memory // 10  # 10% of unused memory


def export_marzban_data() -> None:
    import marzban_models as marzban
    import script_models as models

    clear_console()

    check_marzban_requirements()
    transform_protocol = get_marzban_transform_protocol() == "vless"  # True: vless, False: vmess

    clear_console()

    how_to_dealing_with_non_uuid_users = dealing_with_non_uuid_users()

    clear_console()

    # Get marzban sqlalchemy url by docker compose priority
    with open(MARZBAN_DOCKER_FILE) as f:
        environment = safe_load(f)
    for key in MARZBAN_DOCKER_FILE_ENV_PATH:
        environment = environment.get(key, {})
    sqlalchemy_url = environment.get(MARZBAN_SQLALCHEMY_URL_KEY, None)
    del environment

    repository = RepositoryEnv(MARZBAN_ENV_FILE)
    if sqlalchemy_url is None and MARZBAN_SQLALCHEMY_URL_KEY in repository:
        sqlalchemy_url = repository[MARZBAN_SQLALCHEMY_URL_KEY]
    elif sqlalchemy_url is None:
        sqlalchemy_url = MARZBAN_DEFAULT_SQLALCHEMY_URL

    if MARZBAN_SUBSCRIPTIONS_URL_PREFIX_KEY in repository:
        marzban_subscription_url_prefix = repository[MARZBAN_SUBSCRIPTIONS_URL_PREFIX_KEY]
    else:
        marzban_subscription_url_prefix = MARZBAN_DEFAULT_SUBSCRIPTION_URL_PREFIX
    del repository

    marzban_engine = create_engine(sqlalchemy_url)
    marzban_session = Session(bind=marzban_engine, autoflush=False)

    script_engine = create_engine(f"sqlite:///{DEFAULT_MARZBAN_DATAS_DB_PATH}")
    script_session = Session(bind=script_engine, autoflush=False)

    models.Base.metadata.drop_all(bind=script_engine)
    models.Base.metadata.create_all(bind=script_engine)

    admins = marzban_session.query(marzban.Admin)

    transform_protocols = {
        True: marzban.ProxyTypes.VLESS,
        False: marzban.ProxyTypes.VMess
    }

    tehran_tz = timezone("Asia/Tehran")

    def get_user_key(user_id: int, proxy_type: marzban.ProxyTypes = transform_protocols[transform_protocol]) -> \
    Optional[str]:
        proxy_settings = marzban_session.query(
            marzban.Proxy.settings
        ).filter_by(
            user_id=user_id,
            type=proxy_type
        ).scalar()
        if not proxy_settings and proxy_type == transform_protocols[transform_protocol]:
            return get_user_key(
                user_id,
                transform_protocols[not transform_protocol]
            )

        if proxy_settings:
            user_uuid = proxy_settings.get("id")
            if user_uuid:
                return UUID(user_uuid).hex

    def export_some_marzban_info() -> None:  # use function for make memory empty after exporting
        with Progress(expand=True) as progress:
            for admin in progress.track(admins,
                                        description="Exporting Admins/Users/Users-Node-Usages",
                                        total=admins.count()):
                users: Sequence[marzban.User] = admin.users

                final_users = []
                for user in users:
                    user_key = get_user_key(
                        user_id=user.id  # noqa
                    )

                    if not user_key and how_to_dealing_with_non_uuid_users == "skip":
                        continue

                    if user.status == marzban.UserStatus.on_hold:
                        expire_strategy = models.UserExpireStrategy.START_ON_FIRST_USE
                    elif not user.expire is None:
                        expire_strategy = models.UserExpireStrategy.FIXED_DATE
                    else:
                        expire_strategy = models.UserExpireStrategy.NEVER

                    usage_duration = None
                    activation_deadline = None
                    if user.status == marzban.UserStatus.on_hold:
                        usage_duration = user.on_hold_expire_duration
                        activation_deadline = user.on_hold_timeout
                    # make data_limit integer(I have some None data limits in my marzban)
                    user.data_limit = user.data_limit or 0

                    used_traffic = user.used_traffic or 0
                    if used_traffic > user.data_limit:
                        used_traffic = user.data_limit

                    marzban_user_node_usages = user.node_usages
                    user_node_usages = []
                    for marzban_user_node_usage in marzban_user_node_usages:
                        user_node_usages.append(
                            models.NodeUserUsage(
                                created_at=marzban_user_node_usage.created_at,  # noqa
                                used_traffic=marzban_user_node_usage.used_traffic  # noqa
                            )
                        )

                    if user.expire is not None:
                        expire_date = datetime.fromtimestamp(
                            user.expire,  # noqa
                            tz=datetime_timezone.utc
                        ).astimezone(tehran_tz)
                    else:
                        expire_date = None

                    final_users.append(
                        models.User(
                            username=user.username,
                            key=user_key,
                            enabled=not user.status == marzban.UserStatus.disabled,
                            expire_strategy=expire_strategy,
                            expire_date=expire_date,
                            usage_duration=usage_duration,
                            activation_deadline=activation_deadline,
                            data_limit=user.data_limit,
                            data_limit_reset_strategy=models.UserDataUsageResetStrategy(
                                user.data_limit_reset_strategy.value),
                            note=user.note,
                            used_traffic=used_traffic,
                            lifetime_used_traffic=user.lifetime_used_traffic,
                            sub_updated_at=user.sub_updated_at,
                            sub_revoked_at=user.sub_revoked_at,
                            sub_last_user_agent=user.sub_last_user_agent,
                            created_at=user.created_at,
                            online_at=user.online_at,
                            edit_at=user.edit_at,
                            node_usages=user_node_usages,  # noqa
                        )
                    )

                script_session.add(
                    models.Admin(
                        username=admin.username,
                        hashed_password=admin.hashed_password,
                        users=final_users,  # noqa
                        created_at=admin.created_at,
                        is_sudo=admin.is_sudo,
                        password_reset_at=admin.password_reset_at,
                        subscription_url_prefix=marzban_subscription_url_prefix
                    )
                )

    def export_system_and_node_usages() -> None:  # use function for make memory empty after exporting
        system_info = marzban_session.query(
            marzban.System
        ).scalar()
        script_session.add(
            models.System(
                uplink=system_info.uplink,
                downlink=system_info.downlink
            )
        )
        info("System Uplink and Downlink are exported")
        print("\n\n")

        jwt_token = marzban_session.query(
            marzban.JWT.secret_key
        ).scalar()

        script_session.add(
            models.JWT(
                secret_key=jwt_token
            )
        )
        info("JWT Token is exported")
        print("\n\n")

        node_usages = marzban_session.query(
            marzban.NodeUsage
        )

        with Progress(expand=True) as progress:
            for node_usage in progress.track(node_usages, description="Exporting node-usages",
                                             total=node_usages.count()):
                script_session.add(
                    models.NodeUsage(
                        created_at=node_usage.created_at,  # noqa
                        uplink=node_usage.uplink,  # noqa
                        downlink=node_usage.downlink  # noqa
                    )
                )

    export_some_marzban_info()
    info("Admins, Users, Users-Node-Usages exported successfully.")

    print("\n\n")
    export_system_and_node_usages()
    info("Node usages exported successfully.")

    try:
        script_session.commit()
    except Exception as e:
        error(str(e))
    else:
        info("Marzban database exported successfully")

    print("\n\n")
    input("Press Enter to continue...")


def import_marzban_data() -> None:
    import marzneshin_models as marzneshin
    import script_models as models

    clear_console()

    check_marzneshin_requirements()
    datas_path = get_marzneshin_datas_db_path()

    clear_console()

    how_to_deal_with_existing_admins = dealing_with_existing_admin()

    clear_console()

    how_to_deal_with_existing_users = dealing_with_existing_users()

    clear_console()

    with open(MARZNESHIN_DOCKER_FILE) as f:
        environment = safe_load(f)
    for key in MARZNESHIN_DOCKER_FILE_ENV_PATH:
        environment = environment.get(key, {})
    sqlalchemy_url = environment.get(MARZNESHIN_SQLALCHEMY_URL_KEY, None)
    print(sqlalchemy_url)
    del environment

    repository = RepositoryEnv(MARZNESHIN_ENV_FILE)
    if sqlalchemy_url is None and MARZNESHIN_SQLALCHEMY_URL_KEY in repository:
        sqlalchemy_url = repository[MARZNESHIN_SQLALCHEMY_URL_KEY]
    elif sqlalchemy_url is None:
        sqlalchemy_url = MARZNESHIN_DEFAULT_SQLALCHEMY_URL
    del repository

    marzneshin_engine = create_engine(sqlalchemy_url)
    marzneshin_session = Session(bind=marzneshin_engine, autoflush=False)

    script_engine = create_engine("sqlite:///" + datas_path)
    script_session = Session(bind=script_engine, autoflush=False)

    node = marzneshin_session.query(
        marzneshin.Node
    ).scalar()
    if node is None:
        error("No node exists, please create a node first.")

    inbounds = marzneshin_session.query(
        marzneshin.Inbound
    ).all()
    if not inbounds:
        error("No inbound exists, please create an inbound first.")

    admins = script_session.query(
        models.Admin
    )

    def import_some_marzban_info() -> None:
        with Progress(expand=True) as progress:
            for admin in progress.track(admins,
                                        description="Importing Admins/Users/Useres-Node-Usages",
                                        total=admins.count()):
                admin_exists = marzneshin_session.query(
                    marzneshin_session.query(
                        marzneshin.Admin
                    ).filter_by(
                        username=admin.username
                    ).exists()
                ).scalar()

                if how_to_deal_with_existing_admins == "skip" and admin_exists:
                    continue

                while admin_exists and how_to_deal_with_existing_admins == "rename":
                    last_username_part: str = username.split("_")[-1]
                    if last_username_part.isdigit():
                        number = str(int(last_username_part) + 1)
                        admin.username = username[:-(len(last_username_part) + 1)] + "_" + number
                        if len(admin.username) > 32: # noqa
                            admin.username = admin.username[:31 - len(number)] + "_" + number
                    else:
                        admin.username += "_" + "1"
                    info(f"Admin({username})s username changes to {admin.username}")
                    admin_exists = marzneshin_session.query(
                        marzneshin_session.query(
                            marzneshin.Admin
                        ).filter_by(
                            username=admin.username
                        ).exists()
                    ).scalar()

                services = []
                if how_to_deal_with_existing_admins == "update" and admin_exists:
                    services = marzneshin_session.query(
                        marzneshin.Service
                    ).where(
                        marzneshin.Service.id.in_(
                            marzneshin_session.query(
                                marzneshin.admins_services.c.service_id
                            ).where(
                                marzneshin.admins_services.c.admin_id == marzneshin_session.query( # noqa
                                    marzneshin.Admin.id
                                ).where(
                                    marzneshin.Admin.username == admin.username
                                ).scalar_subquery()
                            )
                        )
                    ).all()

                if not services:
                    service_name = admin.username
                    service_exists = marzneshin_session.query(
                        marzneshin_session.query(
                            marzneshin.Service
                        ).filter_by(
                            name=service_name
                        ).exists()
                    ).scalar()
                    while service_exists:
                        last_name_part = service_name.split("_")[-1]
                        if last_name_part.isdigit():
                            number = int(last_name_part) + 1
                            service_name = service_name[:-(len(last_name_part) + 1)] + "_" + str(number)
                            if len(service_name) > 64:
                                service_name = service_name[:63 - len(str(number))] + "_" + str(number)
                        else:
                            service_name += "_" + "1"
                        service_exists = marzneshin_session.query(
                            marzneshin_session.query(
                                marzneshin.Service
                            ).filter_by(
                                name=service_name
                            ).exists()
                        ).scalar()

                    services = [
                        marzneshin.Service(
                            name=service_name,
                            inbounds=inbounds # noqa
                        )
                    ]

                users: Sequence[models.User] = admin.users

                if how_to_deal_with_existing_admins == "update" and admin_exists:
                    final_users = list(
                        marzneshin_session.query(
                            marzneshin.User
                        ).where(
                            marzneshin.User.admin_id == marzneshin_session.query(
                                marzneshin.Admin.id
                            ).where(
                                marzneshin.Admin.username == admin.username
                            ).scalar_subquery()
                        ).all()
                    )
                else:
                    final_users = []
                for user in users:
                    user_exists = marzneshin_session.query(
                        marzneshin_session.query(
                            marzneshin.User
                        ).filter_by(
                            username=user.username
                        ).exists()
                    ).scalar()

                    if user_exists and how_to_deal_with_existing_users == "skip":
                        continue

                    user_node_usages = []
                    for node_usages in user.node_usages:
                        node_usage = marzneshin_session.query(
                            marzneshin.NodeUserUsage
                        ).filter_by(
                            created_at=node_usages.created_at,
                            user_id=user.id
                        ).scalar()
                        if node_usage:
                            node_usage.used_traffic += node_usages.used_traffic
                        else:
                            node_usage = marzneshin.NodeUserUsage(
                                created_at=node_usages.created_at,
                                node=node, # noqa
                                used_traffic=node_usages.used_traffic
                            )
                        user_node_usages.append(
                            node_usage
                        )

                    if user_exists and how_to_deal_with_existing_users == "update":
                        marzneshin_session.query(
                            update(
                                marzneshin.User
                            ).filter_by(
                                username=user.username
                            ).values(
                                key=user.key,
                                enabled=user.enabled,
                                services=services,
                                used_traffic=user.used_traffic,
                                lifetime_used_traffic=user.lifetime_used_traffic,
                                traffic_reset_at=user.traffic_reset_at,
                                node_usages=user_node_usages,
                                data_limit=user.data_limit,
                                data_limit_reset_strategy=user.data_limit_reset_strategy.value,
                                expire_strategy=user.expire_strategy,
                                expire_date=user.expire_date,
                                usage_duration=user.usage_duration,
                                activation_deadline=user.activation_deadline,
                                sub_updated_at=user.sub_updated_at,
                                sub_revoked_at=user.sub_revoked_at,
                                sub_last_user_agent=user.sub_last_user_agent,
                                created_at=user.created_at,
                                online_at=user.online_at,
                                edit_at=user.edit_at,
                                note=user.note
                            )
                        )
                        user = marzneshin_session.query(
                            marzneshin.User
                        ).filter_by(
                            username=user.username
                        ).scalar()

                    else:
                        if user_exists:  # and how_to_deal_with_existing_users == "rename"
                            clean = sub(r"[^\w]", "", user.username.lower())
                            hash_str = str(int(md5(user.username.encode()).hexdigest(), 16) % 10000).zfill(4)
                            username = f"{clean}_{hash_str}"[:32]
                        else:
                            username = user.username

                        user = marzneshin.User(
                            username=username,
                            key=user.key,
                            enabled=user.enabled,
                            services=services, # noqa
                            used_traffic=user.used_traffic,
                            lifetime_used_traffic=user.lifetime_used_traffic,
                            traffic_reset_at=user.traffic_reset_at,
                            node_usages=user_node_usages, # noqa
                            data_limit=user.data_limit,
                            data_limit_reset_strategy=user.data_limit_reset_strategy.value,
                            expire_strategy=user.expire_strategy,
                            expire_date=user.expire_date,
                            usage_duration=user.usage_duration,
                            activation_deadline=user.activation_deadline,
                            sub_updated_at=user.sub_updated_at,
                            sub_revoked_at=user.sub_revoked_at,
                            sub_last_user_agent=user.sub_last_user_agent,
                            created_at=user.created_at,
                            online_at=user.online_at,
                            edit_at=user.edit_at,
                            note=user.note
                        )
                    final_users.append(
                        user
                    )

                if how_to_deal_with_existing_admins  == "update" and admin_exists:
                    marzneshin_session.query(
                        update(
                            marzneshin.Admin
                        ).filter_by(
                            username=admin.username
                        ).values(
                            hashed_password=admin.hashed_password,
                            users=final_users,
                            services=services,
                            all_services_access=admin.is_sudo,
                            created_at=admin.created_at,
                            is_sudo=admin.is_sudo,
                            password_reset_at=admin.password_reset_at,
                            subscription_url_prefix=admin.subscription_url_prefix
                        )
                    )
                else:
                    marzneshin_session.add(
                        marzneshin.Admin(
                            username=admin.username,
                            hashed_password=admin.hashed_password,
                            users=final_users, # noqa
                            services=services, # noqa
                            all_services_access=admin.is_sudo,
                            created_at=admin.created_at,
                            is_sudo=admin.is_sudo,
                            password_reset_at=admin.password_reset_at,
                            subscription_url_prefix=admin.subscription_url_prefix
                        )
                    )

    def import_system_and_node_usages() -> None:
        system_info = script_session.query(
            models.System
        ).scalar()
        marzneshin_system_info = marzneshin_session.query(
            marzneshin.System
        ).scalar()
        marzneshin_system_info.uplink += system_info.uplink
        marzneshin_system_info.downlink += system_info.downlink

        info("System Uplink and Downlink are updated")
        print("\n\n")

        node_usages = script_session.query(
            models.NodeUsage
        )

        with Progress(expand=True) as progress:
            for node_usage in progress.track(node_usages, description="Importing node-usages",
                                             total=node_usages.count()):
                db_node_usage = marzneshin_session.query(
                    marzneshin.NodeUsage
                ).filter_by(
                    created_at=node_usage.created_at,
                    node_id=node.id
                ).scalar()
                if db_node_usage:
                    db_node_usage.uplink += node_usage.uplink
                    db_node_usage.downlink += node_usage.downlink
                else:
                    marzneshin_session.add(
                        marzneshin.NodeUsage(
                            created_at=node_usage.created_at,
                            uplink=node_usage.uplink,
                            downlink=node_usage.downlink,
                            node=node # noqa
                        )
                    )

    import_some_marzban_info()
    info("Admins, Users, Users-Node-Usage imported successfully.")

    print("\n\n")
    import_system_and_node_usages()
    info("Node usages import successfully.")

    try:
        marzneshin_session.commit()
    except Exception as e:
        error(str(e), do_exit=False)
    else:
        info("Marzban database exported successfully")

    marzban_jwt_token = script_session.query(
        models.JWT.secret_key
    ).scalar()

    # add jwt token to project config
    if not exists(JWT_FILE_PATH):
        if not exists(SCRIPTS_DIR):
            mkdir(SCRIPTS_DIR)
        if not exists(CONFIG_DIR):
            mkdir(CONFIG_DIR)
        if not exists(SCRIPT_CONFIG_DIR):
            mkdir(SCRIPT_CONFIG_DIR)
        tokens = []
    else:
        try:
            with open(JWT_FILE_PATH, "r") as f:
                tokens = f.read().splitlines()
        except: # noqa
            tokens = []

    if marzban_jwt_token not in tokens:
        tokens.append(marzban_jwt_token)

    with open(JWT_FILE_PATH, "w") as f:
        f.write("\n".join(tokens))
    info("Marzban JWT Token added to config successfully")

    if not exists(SCRIPT_DIR):
        if not exists(SCRIPTS_DIR):
            mkdir(SCRIPTS_DIR)
        if not exists(SCRIPT_DIR):
            mkdir(SCRIPT_DIR)

    download_chunk_size = chunk_size()
    try:
        with stream("GET", SOURCE_UPDATER_FILE, follow_redirects=True) as stream_download:
            stream_download.raise_for_status()
            with open(SOURCE_UPDATER_FILE_PATH, "wb") as file:
                for chunk in stream_download.iter_bytes(download_chunk_size):
                    file.write(chunk)
    except HTTPError as e:
        error(str(e), do_exit=False)

    else:
        with open(SOURCE_UPDATER_SYSTEMD_PATH, "w") as f:
            f.write(SOURCE_UPDATER_SYSTEMD_CONTENT)
    warning(f"Please Enable And Start {SCRIPT_NAME} service(`systemctl daemon-reload; systemctl enable {SCRIPT_NAME}; systemctl restart {SCRIPT_NAME}`)")

    print("\n\n")
    input("Press Enter to continue...")


if __name__ == '__main__':
    panel()





















