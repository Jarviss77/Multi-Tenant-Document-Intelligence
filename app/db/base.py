# app/db/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def load_all_models():
    # Import models ONLY for side-effect registration
    import app.db.models.tenant  # noqa
    import app.db.models.document  # noqa
    import app.db.models.embedding_job  # noqa