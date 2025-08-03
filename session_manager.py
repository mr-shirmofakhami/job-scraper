# session_manager.py
from models import Session as DBSession, JobListing, UserSession
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, distinct


class SessionJobManager:
    def __init__(self):
        pass

    def get_or_create_session(self, session_id):
        """Get or create a session record"""
        db = DBSession()
        try:
            user_session = db.query(UserSession).filter_by(session_id=session_id).first()

            if not user_session:
                user_session = UserSession(session_id=session_id)
                db.add(user_session)
            else:
                user_session.last_accessed = datetime.now()

            db.commit()
            return session_id
        finally:
            db.close()

    def save_session_jobs(self, session_id, jobs, search_keyword):
        """Save jobs for a specific session with proper duplicate handling"""
        db = DBSession()
        saved_count = 0

        try:
            for job in jobs:
                try:
                    # Handle both 'city' and 'location' field names
                    city_value = job.get('city') or job.get('location') or 'نامشخص'

                    # First check if this job already exists for this session
                    existing = db.query(JobListing).filter_by(
                        session_id=session_id,
                        link=job.get('link', '')
                    ).first()

                    if existing:
                        # Update existing job if needed
                        existing.title = job.get('title', existing.title)
                        existing.company = job.get('company', existing.company)
                        existing.city = city_value
                        existing.search_keyword = search_keyword
                        print(f"Updated existing job: {existing.title}")
                    else:
                        # Create new job
                        job_listing = JobListing(
                            session_id=session_id,
                            title=job.get('title', 'نامشخص'),
                            company=job.get('company', 'نامشخص'),
                            city=city_value,
                            link=job.get('link', ''),
                            source=job.get('source', ''),
                            search_keyword=search_keyword
                        )
                        db.add(job_listing)
                        saved_count += 1

                    # Commit after each job to avoid bulk constraint errors
                    db.commit()

                except Exception as e:
                    db.rollback()  # Rollback the failed transaction
                    print(f"Error saving job: {e}")
                    print(f"Job data: {job}")
                    continue

        except Exception as e:
            db.rollback()
            print(f"Error in save_session_jobs: {e}")
        finally:
            db.close()

        print(f"Successfully saved {saved_count} new jobs")
        return saved_count

    def clear_session_jobs(self, session_id):
        """Clear all jobs for a specific session"""
        db = DBSession()
        try:
            # Delete in batches to avoid locking issues
            jobs_to_delete = db.query(JobListing).filter_by(session_id=session_id).all()
            count = len(jobs_to_delete)

            for job in jobs_to_delete:
                db.delete(job)

            db.commit()
            print(f"Cleared {count} jobs for session {session_id}")
        except Exception as e:
            db.rollback()
            print(f"Error clearing session jobs: {e}")
        finally:
            db.close()

    def get_session_jobs(self, session_id, source=None, city=None, company=None):
        """Get jobs for a specific session with optional filters"""
        db = DBSession()
        try:
            query = db.query(JobListing).filter_by(
                session_id=session_id,
                is_active=True
            )

            if source:
                query = query.filter_by(source=source)

            if city:
                query = query.filter(JobListing.city.contains(city))

            if company:
                query = query.filter(JobListing.company.contains(company))

            jobs = query.order_by(JobListing.created_at.desc()).all()

            # Convert to dict
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    'id': job.id,
                    'title': job.title,
                    'company': job.company,
                    'city': job.city,
                    'link': job.link,
                    'source': job.source,
                    'search_keyword': job.search_keyword,
                    'created_at': job.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })

            return jobs_data
        finally:
            db.close()

    def get_session_filters(self, session_id):
        """Get available filter options for a session"""
        db = DBSession()
        try:
            # Get unique cities
            cities = db.query(distinct(JobListing.city)).filter(
                and_(
                    JobListing.session_id == session_id,
                    JobListing.is_active == True,
                    JobListing.city != ''
                )
            ).all()

            # Get unique companies
            companies = db.query(distinct(JobListing.company)).filter(
                and_(
                    JobListing.session_id == session_id,
                    JobListing.is_active == True,
                    JobListing.company != ''
                )
            ).all()

            return {
                'cities': sorted([city[0] for city in cities if city[0]]),
                'companies': sorted([company[0] for company in companies if company[0]])
            }
        finally:
            db.close()

    def cleanup_old_sessions(self, days=7):
        """Clean up sessions older than specified days"""
        db = DBSession()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            # Get old sessions
            old_sessions = db.query(UserSession).filter(
                UserSession.last_accessed < cutoff_date
            ).all()

            count = len(old_sessions)

            # Delete old session jobs and sessions
            for session in old_sessions:
                db.query(JobListing).filter_by(session_id=session.session_id).delete()
                db.delete(session)

            db.commit()
            return count
        finally:
            db.close()