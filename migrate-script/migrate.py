"""
Migrate script for migrating from marzban to marzneshin
"""

from contextlib import contextmanager
from datetime import datetime, timezone as datetime_timezone
from hashlib import md5
from inspect import isfunction
from os import mkdir, system as os_system
from os.path import exists
from random import choices
from re import sub
from sqlite3 import connect, Error
from string import ascii_letters, digits
from sys import exit as sys_exit
from typing import Callable, Optional, TypeVar, Union
from uuid import UUID

from decouple import RepositoryEnv
from pytz import timezone
from rich import get_console
from rich.progress import _TrackThread, Progress  # noqa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from yaml import safe_load

# variables
GITHUB_URL = "https://www.github.com/MrAryanDev"
TELEGRAM_URL = "https://t.me/MrAryanDevChan"

REPO_NAME = "marzban2marzneshin"
REPO_URL = f"{GITHUB_URL}/{REPO_NAME}"

SCRIPTS_DIR = "/opt/MrAryanDev"
SCRIPT_DB_PATH = "/root/marzban2marzneshin.db"

PYTHON_EXECUTABLE = f"{SCRIPTS_DIR}/.venv/bin/python"
CONFIGS_DIR = f"{SCRIPTS_DIR}/.config"
SCRIPT_DIR = f"{SCRIPTS_DIR}/{REPO_NAME}"

CONFIG_DIR = f"{CONFIGS_DIR}/{REPO_NAME}"

SOURCE_UPDATER_SYSTEMD_PATH = f"/etc/systemd/system/{REPO_NAME}.service"

JWT_FILE_PATH = f"{CONFIG_DIR}/jwt.txt"


SOURCE_UPDATER_FILE_PATH = f"{SCRIPT_DIR}/update_subscription_source.py"
SOURCE_UPDATER_LOG_PATH = f"{SCRIPT_DIR}/log.txt"

SOURCE_UPDATER_SYSTEMD_CONTENT = f"""[Unit]
Description={REPO_NAME} Service
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


MARZBAN_ENV_PATH = "/opt/marzban/.env"
MARZBAN_DOCKER_COMPOSE_PATH = "/opt/marzban/docker-compose.yml"
MARZBAN_DOCKER_COMPOSE_ENV_PATH = ("services", "marzban", "environment")
MARZBAN_DB_KEY = "SQLALCHEMY_DATABASE_URL"
MARZBAN_SUBSCRIPTION_URL_PREFIX_KEY = "SUBSCRIPTION_URL_PREFIX"
MARZBAN_DEFAULT_SUBSCRIPTION_URL_PREFIX = ""

MARZNESHIN_ENV_PATH = "/etc/opt/marzneshin/.env"
MARZNESHIN_DOCKER_COMPOSE_PATH = "/etc/opt/marzneshin/docker-compose.yml"
MARZNESHIN_DOCKER_COMPOSE_ENV_PATH = ("services", "marzneshin", "environment")
MARZNESHIN_DB_KEY = "SQLALCHEMY_DATABASE_URL"


CONSOLE = get_console()
CONSOLE.style = "bold"

_T = TypeVar("_T")


def clear() -> None:
    """
    Clear the terminal
    """
    CONSOLE.clear()


def get_input(question: str) -> str:
    """
    Get the user input
    """
    return CONSOLE.input(f"[blue]>[/] [yellow]{question}[/][white]?[/] ")


def error(message: str, do_exit: bool = False) -> None:
    """
    Print an error message
    """
    CONSOLE.print(f"[red]Error:[/] [yellow]{message.capitalize()}[/].")
    if do_exit:
        sys_exit(1)


def warning(message: str) -> None:
    """
    Print a warning message
    """
    CONSOLE.print(f"[#ffa500]Warning:[/] [yellow]{message.capitalize()}[/].")


def info(message: str) -> None:
    """
    Print an info message
    """
    CONSOLE.print(f"[#00FFFF]Info:[/] [yellow]{message.capitalize()}[/].")


def selector(title: str, *args: str, **kwargs) -> str:
    """
    Select an option from the given options
    """
    if all((len(args) != 0, len(kwargs) != 0)):
        raise ValueError("You can only use either args or kwargs, not both")

    if args:
        while True:
            CONSOLE.print(f"[white]{title.capitalize()}[/]")
            for index, option in enumerate(args, start=1):
                CONSOLE.print(f"[blue]{index}.[/] {option.title()}")
            option = get_input("Choose an option")
            if option.isdigit() and 0 < int(option) <= len(args):
                return args[int(option) - 1]
            clear()
            error("Invalid option")

    if kwargs:
        while True:
            CONSOLE.print(f"[white]{title}[/]")
            for index, option in enumerate(kwargs.keys(), start=1):
                # make option from snake_case to human readable
                option = option.replace("_", " ").title()
                CONSOLE.print(f"[blue]{index}.[/] {option}")
            option = get_input("Choose an option")
            if option.isdigit() and 0 < int(option) <= len(kwargs):
                value = kwargs[list(kwargs.keys())[int(option) - 1]]
                if isfunction(value):
                    return value()
                return value
            clear()
            error("Invalid option")


def panel() -> None:
    """
    Main panel for the script
    """
    # clear the terminal
    clear()

    while True:

        # print the welcome message
        CONSOLE.print(f"[bwhite]Welcome to the migration script for {REPO_NAME}[/]")
        print("\n")

        # print the author information
        CONSOLE.print(f"[blue]Author: [/][yellow]{GITHUB_URL}[/]")
        CONSOLE.print(f"[blue]Telegram: [/][yellow]{TELEGRAM_URL}[/]")
        print("\n")

        # print options
        # option = selector("Marzban Exporter", "Marzneshin Importer", "Exit")
        # if option == "Marzban Exporter":
        #     marzban_exporter()
        # elif option == "Marzneshin Importer":
        #     marzneshin_importer()
        # else:
        #     break

        try:
            option = selector(
                "Select an option:",
                marzban_exporter="exporter",
                marzneshin_importer="importer",
                exit=lambda : sys_exit(0),
            )
            if option == "exporter":
                marzban_exporter()
            elif option == "importer":
                marzneshin_importer()
            else:
                error("Invalid option")
        except KeyboardInterrupt:
            sys_exit(0)
        except Exception:  # noqa
            clear()
            CONSOLE.print_exception()
        else:
            clear()




def multiple_exists_check(*args: str) -> bool:
    """
    Check if multiple files exist
    """
    for arg in args:
        if not exists(arg):
            error(f"{arg} does not exist")
            return False
    return True


def check_marzban_requirements() -> None:
    """
    Check the requirements for marzban
    """
    if not multiple_exists_check(MARZBAN_ENV_PATH, MARZBAN_DOCKER_COMPOSE_PATH):
        error("Marzban not found", True)


def check_marzneshin_requirements() -> None:
    """
    Check the requirements for marzneshin
    """
    if not multiple_exists_check(MARZNESHIN_ENV_PATH, MARZNESHIN_DOCKER_COMPOSE_PATH):
        error("Marzneshin not found", True)


@contextmanager
def create_progress_bar(title: str, total: int) -> _TrackThread:
    """
    Create a progress bar
    """
    with Progress(expand=True) as p:
        task_id = p.add_task(title, total=total)
        with _TrackThread(p, task_id, 0.1) as tt:
            try:
                yield tt
            finally:
                pass


def increasing_number_username(
    username: str, exists_checker: Callable[[str], bool], max_length: int = 32
) -> Optional[str]:
    """
    Add some digits to end of username
    """
    number = 1
    if (username_length := len(username)) >= max_length:
        return None

    if username_length == max_length - 1:
        sep = ""
    else:
        sep = "_"

    while True:
        new_username = f"{username}{sep}{number}"
        if not exists_checker(new_username):
            return new_username
        if len(new_username) >= max_length:
            return None
        number += 1


def random_name_generator(
    exists_checker: Callable[[str], bool], max_length: int = 32
) -> Optional[str]:
    """
    Generate a random name
    """
    for count in range(1, max_length + 1):
        name = "".join(choices(ascii_letters + digits, k=count))
        if not exists_checker(name):
            return name
        if len(name) >= max_length:
            return None


def username_hash(username: str) -> str:
    """
    Generate a hash for the username
    """
    return str(int(md5(username.encode()).hexdigest(), 16) % 10000).zfill(4)


def hash_based_username(
    username: str, exists_checker: Callable[[str], bool]
) -> Optional[str]:
    """
    Generate a username by appending a hash to the original username
    """
    base_username = username
    sep = "_"
    hash_str = username_hash(base_username)
    while True:
        username = f"{username}{sep}{hash_str}"
        if len(username) >= 32:
            sep = ""
            username = f"{base_username}{sep}{hash_str}"
            if len(username) >= 32:
                return None
        if not exists_checker(username):
            return username


def check_sqlite_file(file_path: str) -> bool:
    """
    Check if the file is a valid sqlite file
    """
    try:
        conn = connect(file_path)
        conn.execute("SELECT id from admins")
        conn.close()
        return True
    except Error:  # sqlite3.Error
        return False


def get_file_path(
    file_name: str, default_path: str = None, checker: Callable[[str], bool] = exists
) -> str:
    """
    Get the file path
    """
    while True:
        info(f"Default path is {default_path}")
        file_path = get_input(f"Enter the path to the {file_name}")
        file_path = file_path or default_path
        if checker(file_path):
            return file_path
        error(f"{file_path} is invalid")


def exists_checker_generator(
    session: Session, model: _T, return_model: bool = False, main_key: str = "username"
) -> Callable[..., Union[bool, _T]]:
    """
    Check if admin exists
    """

    def f(*args, **kwargs) -> bool:
        """
        Check if the username exists
        """
        if args:
            kwargs.update({main_key: args[0]})
        if return_model:
            return session.query(model).filter_by(**kwargs).first()
        else:
            return session.query(session.query(model).filter_by(**kwargs).exists()).scalar()

    return f


def user_key(
    session: Session, user_id: int, proxy_model, protocol: str, _re_search: bool = True
) -> Optional[str]:
    """
    Generate a key for the user
    """
    proxy_settings = (
        session.query(proxy_model.settings)
        .filter_by(user_id=user_id, type=protocol)
        .scalar()
    )
    if proxy_settings is None and _re_search:
        return user_key(
            session,
            user_id,
            proxy_model,
            "vless" if protocol == "vmess" else "vmess",
            False,
        )

    if not (proxy_settings is None):
        if hasattr(proxy_settings, "get"):
            proxy_uuid = proxy_settings.get("id")
        elif "id" in proxy_settings:
            proxy_uuid = proxy_settings["id"]  # noqa
        else:
            return None
        return UUID(proxy_uuid).hex


def get_total(session: Session, models) -> int:
    admins_count = session.query(models.Admin).count()
    users_count = session.query(models.User).count()
    node_usages_count = session.query(models.NodeUsage).count()
    user_node_usages_count = (
        session.query(models.NodeUserUsage)
        .filter(
            models.NodeUserUsage.user_id.in_(
                session.query(models.User.id).scalar_subquery()
            )
        )
        .count()
    )

    return (
        admins_count + users_count + node_usages_count + user_node_usages_count + 2
    )  # system, jwt token


def marzban_exporter() -> None:
    """
    Export data from marzban
    """
    import marzban_models as marzban
    import script_models as script

    clear()

    check_marzban_requirements()

    # transfer vless or vmess
    warning(
        "It is only possible to transfer users who were using the [u]VLESS[/] or [u]VMESS[/] protocol in Marzban."
    )
    transform_protocol = selector(
        "Which protocol should be the priority for migrate?",
        "vless",
        "vmess",
    )

    clear()

    # non-uuid handling
    warning(
        "It is possible that one or more users have not any VLESS/VMESS uuid in database."
        "\nrevoke: Generate new uuid fot that user."
        "\nskip: Nothing is done."
    )
    non_uuid_handling = selector(
        "What should be done for users who do not have a VLESS/VMESS uuid?",
        "revoke",
        "skip",
    )

    clear()

    # get the database uri and subscription url prefix from docker compose
    with open(MARZBAN_DOCKER_COMPOSE_PATH, encoding="utf-8") as file:
        environment = safe_load(file)
    for key in MARZBAN_DOCKER_COMPOSE_ENV_PATH:
        environment = environment.get(key, {})

    db_uri = environment.get(MARZBAN_DB_KEY)
    subscription_url_prefix = environment.get(MARZBAN_SUBSCRIPTION_URL_PREFIX_KEY)
    del environment

    if any((not db_uri, not subscription_url_prefix)):
        repository = RepositoryEnv(MARZBAN_ENV_PATH)
        if not db_uri and MARZBAN_DB_KEY in repository:
            db_uri = repository[MARZBAN_DB_KEY]
        else:
            error("Database URI not found in .env file", True)

        if (
            not subscription_url_prefix
            and MARZBAN_SUBSCRIPTION_URL_PREFIX_KEY in repository
        ):
            subscription_url_prefix = repository[MARZBAN_SUBSCRIPTION_URL_PREFIX_KEY]
        else:
            subscription_url_prefix = MARZBAN_DEFAULT_SUBSCRIPTION_URL_PREFIX

        del repository

    ms = Session(create_engine(db_uri), autoflush=False)

    __script_engine = create_engine(f"sqlite:///{SCRIPT_DB_PATH}")
    ss = Session(bind=__script_engine)

    script.Base.metadata.drop_all(__script_engine)
    script.Base.metadata.create_all(__script_engine)

    tehran_tz = timezone("Asia/Tehran")

    with create_progress_bar("Exporting users", get_total(ms, marzban)) as progress:
        admins = ms.query(marzban.Admin)
        for admin in admins:

            users = ms.query(marzban.User).filter_by(admin_id=admin.id)
            admin_users = []
            for user in users:

                marzban_user_node_usages = ms.query(marzban.NodeUserUsage).filter_by(
                    user_id=user.id
                )
                user_node_usages = []
                for user_node_usage in marzban_user_node_usages:
                    user_node_usages.append(
                        script.NodeUserUsage(
                            created_at=user_node_usage.created_at,  # noqa
                            used_traffic=user_node_usage.used_traffic,  # noqa
                        )
                    )
                    progress.completed += 1
                del marzban_user_node_usages

                key = user_key(ms, user.id, marzban.Proxy, transform_protocol)  # noqa
                if not key and non_uuid_handling == "skip":
                    continue

                data_limit = user.data_limit or 0
                used_traffic = user.used_traffic or 0
                used_traffic = min(data_limit, used_traffic)
                usage_duration = 0
                activation_deadline = None
                expire_date = None
                if user.status == marzban.UserStatus.on_hold:
                    expire_strategy = script.UserExpireStrategy.START_ON_FIRST_USE
                    usage_duration = user.on_hold_expire_duration
                    activation_deadline = user.on_hold_timeout

                elif not (user.expire is None):
                    expire_strategy = script.UserExpireStrategy.FIXED_DATE
                    expire_date = datetime.fromtimestamp(
                        user.expire, tz=datetime_timezone.utc  # noqa
                    ).astimezone(tehran_tz)
                else:
                    expire_strategy = script.UserExpireStrategy.NEVER

                admin_users.append(
                    script.User(
                        username=user.username,  # noqa
                        key=key,
                        enabled=not user.status == marzban.UserStatus.disabled,
                        expire_strategy=expire_strategy,
                        expire_date=expire_date,
                        usage_duration=usage_duration,
                        activation_deadline=activation_deadline,  # noqa
                        data_limit=data_limit,  # noqa
                        data_limit_reset_strategy=user.data_limit_reset_strategy,
                        note=user.note,  # noqa
                        used_traffic=used_traffic,
                        lifetime_used_traffic=user.lifetime_used_traffic,  # noqa
                        sub_updated_at=user.sub_updated_at,  # noqa
                        sub_revoked_at=user.sub_revoked_at,  # noqa
                        sub_last_user_agent=user.sub_last_user_agent,  # noqa
                        created_at=user.created_at,  # noqa
                        online_at=user.online_at,  # noqa
                        edit_at=user.edit_at,  # noqa
                        node_usages=user_node_usages,  # noqa
                    )
                )
                progress.completed += 1
            del users

            ss.add(
                script.Admin(
                    username=admin.username,  # noqa
                    hashed_password=admin.hashed_password,  # noqa
                    is_sudo=admin.is_sudo,  # noqa
                    password_reset_at=admin.password_reset_at,  # noqa
                    subscription_url_prefix=subscription_url_prefix,  # noqa
                    created_at=admin.created_at,  # noqa
                    users=admin_users,  # noqa
                )
            )
            progress.completed += 1
        del admins

        node_usages = ms.query(marzban.NodeUsage)
        for node_usage in node_usages:

            ss.add(
                script.NodeUsage(
                    created_at=node_usage.created_at,  # noqa
                    uplink=node_usage.uplink,  # noqa
                    downlink=node_usage.downlink,  # noqa
                )
            )
            progress.completed += 1
        del node_usages

        marzban_system = ms.query(marzban.System).first()
        if marzban_system:
            ss.add(
                script.System(
                    uplink=marzban_system.uplink,  # noqa
                    downlink=marzban_system.downlink,  # noqa
                )
            )
        progress.completed += 1
        del marzban_system

        jwt_token = ms.query(marzban.JWT.secret_key).scalar()
        if jwt_token:
            ss.add(
                script.JWT(
                    secret_key=jwt_token,  # noqa
                )
            )
        progress.completed += 1
        del jwt_token

        ss.commit()

    ms.close()

    print("\n\n")
    input("Press Enter to continue...")


def marzneshin_importer() -> None:
    """
    Import data to marzneshin
    """
    import marzneshin_models as marzneshin
    import script_models as script

    clear()

    check_marzneshin_requirements()

    # get the database path
    db_path = get_file_path("Marzban Datastore", SCRIPT_DB_PATH, check_sqlite_file)

    # marzneshin is new(empty) or old(has admin or user)
    marzneshin_status = selector(
        "Is Marzneshin new(no admin and user) or old(has admin or user)?",
        "new",
        "old",
    )

    if not marzneshin_status == "old":
        exists_admins_handling = "skip"
        exists_users_handling = "skip"

    else:
        clear()
        # exists admins handling
        warning(
            f"It is possible that one or more admins already exist."
            f"\nrename: Add some digits to end of username."
            f"\nupdate: Update the current admin info[save username](Non-sudo admins)."
            f"\nskip: Nothing is done."
        )
        exists_admins_handling = selector(
            "What should be done for existing admins?",
            "rename",
            "update",
            "skip",
        )

        clear()
        # exists users handling
        warning(
            f"It is possible that one or more users already exist."
            f"\nrename: Add some characters to end of username."
            f"\nupdate: Update the current user info[save username]."
            f"\nskip: Nothing is done."
        )
        exists_users_handling = selector(
            "What should be done for existing users?",
            "rename",
            "update",
            "skip",
        )

    # get marzneshin database uri
    with open(MARZNESHIN_DOCKER_COMPOSE_PATH, encoding="utf-8") as file:
        environment = safe_load(file)
    for key in MARZNESHIN_DOCKER_COMPOSE_ENV_PATH:
        environment = environment.get(key, {})
    db_uri = environment.get(MARZNESHIN_DB_KEY)
    del environment

    if not db_uri:
        repository = RepositoryEnv(MARZNESHIN_ENV_PATH)
        if MARZNESHIN_DB_KEY in repository:
            db_uri = repository[MARZNESHIN_DB_KEY]
        else:
            error("Database URI not found in .env file", True)
        del repository

    ms = Session(create_engine(db_uri), autoflush=False)
    ss = Session(create_engine(f"sqlite:///{db_path}"))

    first_node_id = ms.query(marzneshin.Node.id).scalar()
    if first_node_id is None:
        error("There is no node in Marzneshin", True)

    inbounds = ms.query(marzneshin.Inbound).all()
    if not inbounds:
        error("There is no inbound in Marzneshin", True)

    get_admin = exists_checker_generator(ms, marzneshin.Admin, True)
    get_user = exists_checker_generator(ms, marzneshin.User, True)
    get_user_node_usage = exists_checker_generator(ms, marzneshin.NodeUserUsage, True)
    get_node_usage = exists_checker_generator(ms, marzneshin.NodeUsage, True)
    check_admin_exists = exists_checker_generator(ms, marzneshin.Admin)
    check_user_exists = exists_checker_generator(ms, marzneshin.User)
    check_service_exists = exists_checker_generator(
        ms, marzneshin.Service, main_key="name"
    )

    clear()


    with create_progress_bar("Importing users", get_total(ss, script)) as progress:
        admins = ss.query(script.Admin)
        for admin in admins:

            admin_username = admin.username
            if exists_admin := get_admin(admin.username):  # noqa
                if exists_admins_handling == "skip":
                    continue
                if exists_admins_handling == "rename":
                    new_username = increasing_number_username(
                        admin.username, check_admin_exists  # noqa
                    )
                    if new_username is None:
                        warning(f"Cannot rename the admin({admin.username})")
                        continue
                    admin_username = new_username
                services = exists_admin.services
            else:
                service_name = f"{admin_username}_service"
                if len(service_name) >= 64:
                    service_name = admin_username[:60]
                if check_service_exists(service_name):
                    service_name = increasing_number_username(
                        service_name, check_service_exists, 64
                    )
                    if service_name is None:
                        warning(
                            "Can't create service that name contains admin username, generating random one"
                        )
                        service_name = random_name_generator(check_service_exists, 64)
                        if service_name is None:
                            error(
                                f"Can't create service for admin({admin.username}), we will skip it"
                            )
                            continue

                services = [
                    marzneshin.Service(name=service_name, inbounds=inbounds)  # noqa
                ]

            users = ss.query(script.User).filter_by(admin_id=admin.id)
            admin_users = []
            for user in users:

                user_username = sub(r"\W", "", user.username.lower())
                if exists_user := get_user(user_username):  # noqa
                    if exists_users_handling == "skip":
                        continue
                    if exists_users_handling == "rename":
                        new_username = hash_based_username(
                            user_username, check_user_exists  # noqa
                        )
                        if new_username is None:
                            warning(f"Cannot rename the user({user_username}")
                            continue
                        user_username = new_username

                if exists_user and exists_users_handling == "update":
                    exists_user.key = user.key
                    exists_user.enabled = user.enabled
                    exists_user.services = services
                    exists_user.used_traffic = user.used_traffic
                    exists_user.lifetime_used_traffic = user.lifetime_used_traffic
                    exists_user.data_limit = user.data_limit
                    exists_user.data_limit_reset_strategy = (
                        user.data_limit_reset_strategy
                    )
                    exists_user.expire_strategy = user.expire_strategy
                    exists_user.expire_date = user.expire_date
                    exists_user.usage_duration = user.usage_duration
                    exists_user.activation_deadline = user.activation_deadline
                    exists_user.sub_updated_at = user.sub_updated_at
                    exists_user.sub_revoked_at = user.sub_revoked_at
                    exists_user.sub_last_user_agent = user.sub_last_user_agent
                    exists_user.created_at = user.created_at
                    exists_user.online_at = user.online_at
                    exists_user.edit_at = user.edit_at
                    exists_user.note = user.note
                    new_user = exists_user
                else:
                    new_user = marzneshin.User(
                        username=user_username,
                        key=user.key,
                        enabled=user.enabled,
                        services=services,  # noqa
                        used_traffic=user.used_traffic,
                        lifetime_used_traffic=user.lifetime_used_traffic,
                        data_limit=user.data_limit,
                        data_limit_reset_strategy=user.data_limit_reset_strategy,
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
                        note=user.note,
                    )
                    ms.add(new_user)
                    ms.flush()
                    ms.refresh(new_user)

                admin_users.append(new_user)
                progress.completed += 1

                user_node_usages = ss.query(script.NodeUserUsage).filter_by(
                    user_id=user.id
                )
                for user_node_usage in user_node_usages:

                    exists_node_user_usage = get_user_node_usage(
                        user_id=new_user.id,
                        created_at=user_node_usage.created_at,
                        node_id=first_node_id,
                    )
                    if exists_node_user_usage:
                        exists_node_user_usage.used_traffic += (
                            user_node_usage.used_traffic
                        )
                    else:
                        ms.add(
                            marzneshin.NodeUserUsage(
                                user_id=new_user.id,
                                created_at=user_node_usage.created_at,  # noqa
                                used_traffic=user_node_usage.used_traffic,  # noqa
                                node_id=first_node_id,  # noqa
                            )
                        )
                    ms.flush()
                    progress.completed += 1
                del user_node_usages
            del users

            if exists_admin and exists_admins_handling == "update":
                exists_admin.hashed_password = admin.hashed_password
                exists_admin.users = admin_users
                exists_admin.services = services
                exists_admin.all_services_access = admin.is_sudo
                exists_admin.created_at = admin.created_at
                exists_admin.is_sudo = admin.is_sudo
                exists_admin.password_reset_at = admin.password_reset_at
                exists_admin.subscription_url_prefix = admin.subscription_url_prefix
            else:
                ms.add(
                    marzneshin.Admin(
                        username=admin_username,
                        hashed_password=admin.hashed_password,
                        users=admin_users,  # noqa
                        services=services,  # noqa
                        all_services_access=admin.is_sudo,
                        created_at=admin.created_at,
                        is_sudo=admin.is_sudo,
                        password_reset_at=admin.password_reset_at,
                        subscription_url_prefix=admin.subscription_url_prefix,
                    )
                )
            progress.completed += 1
        del admins, services, get_admin, get_user
        del (
            get_user_node_usage,
            check_admin_exists,
            check_user_exists,
            check_service_exists,
        )

        node_usages = ss.query(script.NodeUsage)
        for node_usage in node_usages:

            exists_node_usage = get_node_usage(
                created_at=node_usage.created_at, node_id=first_node_id
            )
            if exists_node_usage:
                exists_node_usage.uplink = node_usage.uplink
                exists_node_usage.downlink = node_usage.downlink
            else:
                ms.add(
                    marzneshin.NodeUsage(
                        created_at=node_usage.created_at,  # noqa
                        uplink=node_usage.uplink,  # noqa
                        downlink=node_usage.downlink,  # noqa
                        node_id=first_node_id,  # noqa
                    )
                )
            ms.flush()
            progress.completed += 1
        del node_usages

        marzneshin_system = ms.query(marzneshin.System).first()
        if marzneshin_system:
            system = ss.query(script.System).first()
            marzneshin_system.uplink += system.uplink
            marzneshin_system.downlink += system.downlink
            del system
        progress.completed += 1

        try:
            ms.commit()
        except Exception as e:
            ms.rollback()
            raise e

        marzban_jwt_token = ss.query(script.JWT.secret_key).scalar()

        if not exists(JWT_FILE_PATH):
            if not exists(SCRIPTS_DIR):
                mkdir(SCRIPTS_DIR)
            if not exists(CONFIG_DIR):
                mkdir(CONFIGS_DIR)
            if not exists(CONFIG_DIR):
                mkdir(CONFIG_DIR)
            tokens = set()
        else:
            try:
                with open(JWT_FILE_PATH) as f:
                    tokens = set(f.read().splitlines())
            except:  # noqa
                tokens = set()

        tokens.add(marzban_jwt_token)
        with open(JWT_FILE_PATH, "w") as f:
            f.write("\n".join(tokens))

        progress.completed += 1
    with open(SOURCE_UPDATER_SYSTEMD_PATH, "w") as f:
        f.write(SOURCE_UPDATER_SYSTEMD_CONTENT)

    os_system(
        f"systemctl daemon-reload; systemctl enable {REPO_NAME}; systemctl restart {REPO_NAME}"
    )

    print("\n\n")
    input("Press Enter to continue...")


if __name__ == "__main__":
    panel()
