from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class JobListing(Base):
    __tablename__ = 'job_listings'

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    company = Column(String(300))
    city = Column(String(200))
    link = Column(String(1000))
    source = Column(String(50))  # jobinja or jobvision
    search_keyword = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


# Database setup
engine = create_engine('sqlite:///jobs.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)