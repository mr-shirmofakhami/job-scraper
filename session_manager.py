# session_manager.py
from models import Session as DBSession, JobListing, UserSession
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, distinct


class SessionManager:
    def __init__(self, db_session):
        self.db_session = db_session

    def parse_persian_date(self, date_text):
        """Convert Persian date text to a sortable value"""
        if not date_text or date_text == 'نامشخص':
            return 999  # Unknown dates go to the end

        import re

        if 'امروز' in date_text:
            return 0
        elif 'دیروز' in date_text:
            return 1
        elif 'ساعت' in date_text:
            # Extract hours
            hours = re.findall(r'\d+', date_text)
            return 0.1 if not hours else float(hours[0]) / 24
        elif 'روز' in date_text:
            # Extract days
            days = re.findall(r'\d+', date_text)
            return 2 if not days else int(days[0])
        elif 'هفته' in date_text:
            # Extract weeks
            weeks = re.findall(r'\d+', date_text)
            return 7 if not weeks else int(weeks[0]) * 7
        elif 'ماه' in date_text:
            # Extract months
            months = re.findall(r'\d+', date_text)
            return 30 if not months else int(months[0]) * 30
        else:
            return 999

    def get_session_jobs(self, session_id, source=None, city=None, company=None, sort_by='newest'):
        """Get jobs with sorting options using Persian date parsing"""
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

            jobs = query.all()

            # Convert to dict with date info
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
                    'date_posted': job.date_posted if hasattr(job, 'date_posted') else 'نامشخص',
                    'created_at': job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'date_sort_value': self.parse_persian_date(
                        job.date_posted if hasattr(job, 'date_posted') else 'نامشخص')
                })

            # Sort by Persian date
            if sort_by == 'oldest':
                jobs_data.sort(key=lambda x: x['date_sort_value'], reverse=True)
            else:  # Default to newest
                jobs_data.sort(key=lambda x: x['date_sort_value'])

            return jobs_data
        finally:
            db.close()

    def save_session_jobs(self, session_id, jobs, search_keyword):
        """Save jobs for a specific session with proper duplicate handling"""
        db = DBSession()
        saved_count = 0
        updated_count = 0

        try:
            for job in jobs:
                try:
                    city_value = job.get('city') or job.get('location') or 'نامشخص'
                    date_value = job.get('date', '') or job.get('date_posted', '') or 'نامشخص'

                    # Check if job exists for ANY session (not just this one)
                    existing = db.query(JobListing).filter_by(
                        link=job.get('link', '')
                    ).first()

                    if existing:
                        # Update existing job
                        existing.title = job.get('title', existing.title)
                        existing.company = job.get('company', existing.company)
                        existing.city = city_value
                        existing.date_posted = date_value
                        existing.search_keyword = search_keyword
                        existing.session_id = session_id  # Update to current session
                        existing.is_active = True
                        db.commit()
                        updated_count += 1
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
                            search_keyword=search_keyword,
                            date_posted=date_value
                        )
                        db.add(job_listing)
                        db.commit()
                        saved_count += 1
                        print(f"Saved new job: {job_listing.title}")

                except Exception as e:
                    db.rollback()
                    print(f"Error saving job: {e}")
                    print(f"Job data: {job}")
                    continue

        except Exception as e:
            db.rollback()
            print(f"Error in save_session_jobs: {e}")
        finally:
            db.close()

        print(f"Successfully saved {saved_count} new jobs and updated {updated_count} existing jobs")
        return saved_count + updated_count

    def clear_session_jobs(self, session_id):
        """Clear all jobs for a specific session"""
        db = DBSession()
        try:
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