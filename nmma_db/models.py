"""
Database schema.
"""

from datetime import datetime, date
import simplejson as json
import enum

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from arrow.arrow import Arrow

from nmma_db.utils import load_config, generate_password_hash, check_password_hash

DBSession = scoped_session(sessionmaker())
EXECUTEMANY_PAGESIZE = 50000
utcnow = func.timezone("UTC", func.current_timestamp())

data_types = {
    int: "int",
    float: "float",
    bool: "bool",
    dict: "dict",
    str: "str",
    list: "list",
}

cfg = load_config(config_file="config.yaml")["nmma"]


class Encoder(json.JSONEncoder):
    """Extends json.JSONEncoder with additional capabilities/configurations."""

    def default(self, o):
        if isinstance(o, (datetime, Arrow, date)):
            return o.isoformat()

        elif isinstance(o, bytes):
            return o.decode("utf-8")

        elif hasattr(o, "__table__"):  # SQLAlchemy model
            return o.to_dict()

        elif o is int:
            return "int"

        elif o is float:
            return "float"

        elif type(o).__name__ == "ndarray":  # avoid numpy import
            return o.tolist()

        elif type(o).__name__ == "DataFrame":  # avoid pandas import
            o.columns = o.columns.droplevel("channel")  # flatten MultiIndex
            return o.to_dict(orient="index")

        elif type(o) is type and o in data_types:
            return data_types[o]

        return json.JSONEncoder.default(self, o)


def to_json(obj):
    return json.dumps(obj, cls=Encoder, indent=2, ignore_nan=True)


class BaseMixin(object):
    query = DBSession.query_property()
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    created_at = sa.Column(sa.DateTime, nullable=False, default=utcnow)
    modified = sa.Column(sa.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + "s"

    __mapper_args__ = {"confirm_deleted_rows": False}

    def __str__(self):
        return to_json(self)

    def __repr__(self):
        attr_list = [
            f"{c.name}={getattr(self, c.name)}" for c in self.__table__.columns
        ]
        return f"<{type(self).__name__}({', '.join(attr_list)})>"

    def to_dict(self):
        if sa.inspection.inspect(self).expired:
            DBSession().refresh(self)
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def is_owned_by(self, user):
        raise NotImplementedError("Ownership logic is application-specific")

    @classmethod
    def create_or_get(cls, id):
        obj = cls.query.get(id)
        if obj is not None:
            return obj
        else:
            return cls(id=id)


Base = declarative_base(cls=BaseMixin)


# The db has to be initialized later; this is done by the app itself
# See `app_server.py`
def init_db(
    user,
    database,
    password=None,
    host=None,
    port=None,
    autoflush=True,
    engine_args={},
):
    """
    Parameters
    ----------
    engine_args : dict
        - `pool_size`:
          The number of connections maintained to the DB. Default 5.

        - `max_overflow`:
          The number of additional connections that will be made as needed.
           Once these extra connections have been used, they are discarded.
          Default 10.

        - `pool_recycle`:
           Prevent the pool from using any connection that is older than this
           (specified in seconds).
           Default 3600.

    """
    url = "postgresql://{}:{}@{}:{}/{}"
    url = url.format(user, password or "", host or "", port or "", database)

    default_engine_args = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 3600,
    }
    conn = sa.create_engine(
        url,
        client_encoding="utf8",
        executemany_mode="values",
        executemany_values_page_size=EXECUTEMANY_PAGESIZE,
        **{**default_engine_args, **engine_args},
    )

    DBSession.configure(bind=conn, autoflush=autoflush)
    Base.metadata.bind = conn

    return conn


class User(Base):
    """A simple user class for the database. Should be replaced by
    something in Baselayer eventually."""

    username = sa.Column(sa.String, primary_key=True, nullable=False, doc="Username")

    email = sa.Column(sa.String, nullable=True, doc="User email")

    password_hash = sa.Column(sa.String, nullable=True, doc="Username")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LightcurveFit(Base):
    """A record of an astronomical light curve fit and its metadata,
    such as best fit, parameter distribution, and Bayes factors."""

    object_id = sa.Column(
        sa.String, primary_key=True, nullable=False, doc="Name of object being fit"
    )

    model_name = sa.Column(
        sa.String, primary_key=True, nullable=False, doc="Model name"
    )

    bestfit_lightcurve = sa.Column(
        JSONB,
        nullable=True,
        doc="best fit light curve information.",
    )

    posterior_samples = sa.Column(
        JSONB,
        nullable=True,
        doc="posterior distributions.",
    )

    log_bayes_factor = sa.Column(
        sa.Float, nullable=True, comment="log(Bayes) factor for the run"
    )

    class Status(enum.IntEnum):
        WORKING = 0
        READY = 1

    status = sa.Column(
        sa.Enum(Status), default=Status.WORKING, nullable=False, comment="Plan status"
    )


if __name__ == "__main__":

    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument("-i", "--init_db", action="store_true", default=False)
    parser.add_argument("-p", "--purge", action="store_true", default=False)
    args = parser.parse_args()

    conn = init_db(**cfg["database"])

    if args.init_db:
        print(f"Creating tables on database {conn.url.database}")
        Base.metadata.drop_all()
        Base.metadata.create_all()

        print("Refreshed tables:")
        for m in Base.metadata.tables:
            print(f" - {m}")
