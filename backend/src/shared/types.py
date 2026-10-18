import enum

from sqlalchemy import Enum


def text_enum(enum_cls: type[enum.Enum]) -> Enum:
    """Store enum values as text; the migration owns the CHECK constraints."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=False,
        length=None,
        values_callable=lambda members: [member.value for member in members],
    )
