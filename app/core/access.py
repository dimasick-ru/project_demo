"""Role and record policies shared by the web layer and SQL repository."""

from dataclasses import dataclass

ROLE_LABELS = {
    "manager": "Менеджер",
    "administrator": "Администратор",
    "director": "Руководитель",
}


class AccessDeniedError(Exception):
    """An authenticated employee cannot perform the requested operation."""


OWNED = frozenset(
    {
        "clients",
        "nomenclature",
        "visits",
        "contracts",
        "sales",
        "payments",
        "stock",
        "movements",
        "provided_services",
        "service_log",
    }
)
# A related record follows its client's/product's owner, including after reassignment.
PARENTS = {
    "visits": ("client_id", "clients"),
    "contracts": ("client_id", "clients"),
    "sales": ("client_id", "clients"),
    "stock": ("item_id", "nomenclature"),
    "movements": ("item_id", "nomenclature"),
    "provided_services": ("service_id", "nomenclature"),
    "service_log": ("service_id", "nomenclature"),
}


@dataclass(frozen=True)
class User:
    id: int
    employee_id: int
    username: str
    name: str
    role: str
    csrf_token: str = ""


def can_read(user: User, key: str) -> bool:
    return user.role == "director" or (
        user.role in {"manager", "administrator"} and key in OWNED | {"programs"}
    )


def can_write(user: User, key: str) -> bool:
    return user.role == "director" or (
        user.role in {"manager", "administrator"} and key in OWNED
    )


def require_access(user: User, key: str, *, write: bool = False) -> None:
    if not (can_write(user, key) if write else can_read(user, key)):
        raise AccessDeniedError("У вашей роли нет доступа к этому разделу")
