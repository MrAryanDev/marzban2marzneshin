from sqlalchemy import Integer, Column, String, text, DateTime, Boolean, BigInteger, Enum, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from enum import Enum as EnumSubClass
Base = declarative_base()

class UserDataUsageResetStrategy(str, EnumSubClass):
    no_reset = "no_reset"
    day = "day"
    week = "week"
    month = "month"
    year = "year"

class UserExpireStrategy(str, EnumSubClass):
    NEVER = "never"
    FIXED_DATE = "fixed_date"
    START_ON_FIRST_USE = "start_on_first_use"

class ReminderType(str, EnumSubClass):
    expiration_date = "expiration_date"
    data_usage = "data_usage"


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    hashed_password = Column(String)
    users = relationship("User", back_populates="admin")
    created_at = Column(DateTime)
    is_sudo = Column(Boolean)
    password_reset_at = Column(DateTime)
    subscription_url_prefix = Column(String)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    key = Column(String)
    enabled = Column(
        Boolean
    )
    used_traffic = Column(BigInteger)
    lifetime_used_traffic = Column(
        BigInteger
    )
    traffic_reset_at = Column(DateTime, nullable=True)
    node_usages = relationship(
        "NodeUserUsage",
        back_populates="user"
    )
    notification_reminders = relationship(
        "NotificationReminder",
        back_populates="user"
    )
    data_limit = Column(BigInteger)
    data_limit_reset_strategy = Column(
        Enum(UserDataUsageResetStrategy)
    )
    expire_strategy = Column(
        Enum(UserExpireStrategy)
    )
    expire_date = Column(DateTime)
    usage_duration = Column(BigInteger)
    activation_deadline = Column(DateTime)
    admin_id = Column(Integer, ForeignKey("admins.id"))
    admin = relationship("Admin", back_populates="users")
    sub_updated_at = Column(DateTime)
    sub_last_user_agent = Column(String)
    sub_revoked_at = Column(DateTime)
    created_at = Column(DateTime)
    note = Column(String)
    online_at = Column(DateTime)
    edit_at = Column(DateTime)



class NodeUserUsage(Base):
    __tablename__ = "node_user_usages"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="node_usages")
    used_traffic = Column(BigInteger)

class NotificationReminder(Base):
    __tablename__ = "notification_reminders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="notification_reminders")
    type = Column(Enum(ReminderType))
    expires_at = Column(DateTime)
    created_at = Column(DateTime)


class System(Base):
    __tablename__ = "system"

    id = Column(Integer, primary_key=True)
    uplink = Column(BigInteger)
    downlink = Column(BigInteger)

class NodeUsage(Base):
    __tablename__ = "node_usages"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)  # one hour per record
    uplink = Column(BigInteger)
    downlink = Column(BigInteger)

class JWT(Base):
    __tablename__ = "jwt"

    id = Column(Integer, primary_key=True)
    secret_key = Column(
        String(64)
    )
