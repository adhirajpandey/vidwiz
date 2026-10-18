def import_models() -> None:
    """Import every ORM module so Base.metadata lists all tables."""
    from src.auth import models as auth_models  # noqa: F401
    from src.conversations import models as conversation_models  # noqa: F401
    from src.credits import models as credits_models  # noqa: F401
    from src.internal import models as internal_models  # noqa: F401
    from src.notes import models as notes_models  # noqa: F401
    from src.payments import models as payments_models  # noqa: F401
    from src.videos import models as video_models  # noqa: F401
