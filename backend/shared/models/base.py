"""
Shared SQLAlchemy declarative base.

Keeping Base in a dedicated module avoids circular imports between model modules.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

