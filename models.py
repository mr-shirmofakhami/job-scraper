# models.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

# Database setup
engine = create_engine('sqlite:///data/jobs.db', echo=False)
Session = sessionmaker(bind=engine)


class JobListing(Base):
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    company = Column(String(200))
    city = Column(String(100))
    link = Column(String(500), unique=True)
    source = Column(String(50))
    search_keyword = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    is_active = Column(Boolean, default=True)
    session_id = Column(String(100), index=True)  # Add session support

    __table_args__ = (
        UniqueConstraint('session_id', 'link', name='_session_link_uc'),
    )


class UserSession(Base):
    __tablename__ = 'user_sessions'

    session_id = Column(String(100), primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    last_accessed = Column(DateTime, default=datetime.now)
    search_count = Column(Integer, default=0)


# Create tables
Base.metadata.create_all(engine)