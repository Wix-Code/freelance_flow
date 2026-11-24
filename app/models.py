
from datetime import datetime
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func, Numeric, Text,
    ForeignKeyConstraint,
    Date,
    CheckConstraint,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    clients: Mapped[list["Client"]] = relationship(
        back_populates="owner"
    )
    
    projects: Mapped[list["Project"]] = relationship(
        back_populates="owner"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    user: Mapped["User"] = relationship(
        back_populates="refresh_tokens"
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    company: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    owner: Mapped["User"] = relationship(
        back_populates="clients"
    )
    
    projects: Mapped[list["Project"]] = relationship(
        back_populates="client"
    )
    
    
class Project(Base):
    __tablename__ = "projects"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "owner_id",
            name="uq_projects_id_owner"
        ),
        CheckConstraint(
            "budget > 0",
            name="ck_projects_budget_positive"
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_projects_status"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    budget: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )

    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    client_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "id",
            "owner_id",
            name="uq_projects_id_owner"
        ),
        CheckConstraint(
            "budget > 0",
            name="ck_projects_budget_positive"
        ),
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="ck_projects_status"
        ),
        # The pair ensures the referenced client
        # belongs to the same owner.
        ForeignKeyConstraint(
            ["client_id", "owner_id"],
            ["clients.id", "clients.owner_id"],
            name="fk_projects_client_owner"
        ),
        
        UniqueConstraint(
            "id",
            "owner_id",
            name="uq_projects_id_owner"
        ),
    )

    owner: Mapped["User"] = relationship(
        back_populates="projects"
    )

    client: Mapped["Client"] = relationship(
        back_populates="projects",
        foreign_keys=[client_id, owner_id],
        overlaps="owner,projects"
    )
    
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        foreign_keys="[Task.project_id, Task.owner_id]",
        overlaps="owner,project,tasks"
    )
    

class Task(Base):
    __tablename__ = "tasks"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed')",
            name="ck_tasks_status"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_tasks_priority"
        ),
        ForeignKeyConstraint(
            ["project_id", "owner_id"],
            ["projects.id", "projects.owner_id"],
            name="fk_tasks_project_owner",
            ondelete="CASCADE"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )

    priority: Mapped[str] = mapped_column(
        String(10),
        default="medium",
        nullable=False
    )

    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    project_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    owner_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    project: Mapped["Project"] = relationship(
        back_populates="tasks",
        foreign_keys=[project_id, owner_id],
        overlaps="tasks"
    )

