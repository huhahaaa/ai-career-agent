from sqlalchemy.engine import Engine

import app.models  # noqa: F401
from app.db.session import Base, engine


def init_db(bind: Engine = engine) -> None:
    Base.metadata.create_all(bind=bind)
