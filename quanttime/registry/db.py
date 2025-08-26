from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from quanttime.utils.config import AppConfig


Base = declarative_base()


def get_engine(cfg: AppConfig):
    return create_engine(cfg.database_url, echo=False, future=True)


def get_session_factory(cfg: AppConfig):
    engine = get_engine(cfg)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


