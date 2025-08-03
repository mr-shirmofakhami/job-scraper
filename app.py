from flask import Flask, render_template, request, jsonify, session
from flask_session import Session as FlaskSession
import uuid
import os
from datetime import datetime, timedelta
from job_scraper import JobScraper
from session_manager import SessionJobManager
from models import Session as DBSession, JobListing
import threading

app = Flask(__name__)

# Configure session
app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './data/sessions'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# Initialize Flask-Session
FlaskSession(app)

# Create sessions directory
os.makedirs('./data/sessions', exist_ok=True)

# Global variable to track scraping status
scraping_status = {'is_scraping': False, 'message': ''}

# Initialize session manager
session_manager = SessionJobManager()


@app.route('/')
def index():
    # Get or create session
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['created_at'] = datetime.now().isoformat()

    session_id = session_manager.get_or_create_session(session['session_id'])
    return render_template('index.html', session_id=session_id)


@app.route('/api/scrape', methods=['POST'])
def scrape_jobs():
    global scraping_status

    if scraping_status['is_scraping']:
        return jsonify({'error': 'جستجو در حال انجام است'}), 400

    data = request.json
    keyword = data.get('keyword', '').strip()
    sources = data.get('sources', [])

    # Get session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']

    if not keyword:
        return jsonify({'error': 'کلمه کلیدی الزامی است'}), 400

    if not sources:
        return jsonify({'error': 'حداقل یک منبع باید انتخاب شود'}), 400

    # Start scraping in background
    scraping_status['is_scraping'] = True
    scraping_status['message'] = 'شروع جستجو...'

    def scrape_in_background():
        global scraping_status
        try:
            scraper = JobScraper(session_manager=session_manager)
            total_jobs = scraper.scrape_all(keyword, sources, session_id=session_id)
            scraping_status['message'] = f'تعداد {total_jobs} آگهی یافت شد'
        except Exception as e:
            scraping_status['message'] = f'خطا: {str(e)}'
        finally:
            scraping_status['is_scraping'] = False

    thread = threading.Thread(target=scrape_in_background)
    thread.start()

    return jsonify({'message': 'جستجو شروع شد', 'session_id': session_id})


@app.route('/api/status')
def get_status():
    return jsonify(scraping_status)


@app.route('/api/jobs')
def get_jobs():
    # Get session ID
    session_id = session.get('session_id')
    if not session_id:
        return jsonify([])

    # Get filter parameters
    city = request.args.get('city', '')
    company = request.args.get('company', '')
    source = request.args.get('source', '')

    # Get jobs for this session
    jobs = session_manager.get_session_jobs(session_id, source, city, company)

    return jsonify(jobs)


@app.route('/api/filters')
def get_filters():
    # Get session ID
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'cities': [], 'companies': []})

    # Get filters for this session
    filters = session_manager.get_session_filters(session_id)

    return jsonify(filters)


@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    """Clear current session's jobs"""
    session_id = session.get('session_id')
    if session_id:
        session_manager.clear_session_jobs(session_id)

    return jsonify({'message': 'نتایج پاک شد', 'session_id': session_id})


@app.route('/api/session-info')
def session_info():
    """Get current session information"""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'session_id': None, 'job_count': 0})

    db = DBSession()
    try:
        job_count = db.query(JobListing).filter_by(session_id=session_id).count()

        return jsonify({
            'session_id': session_id,
            'job_count': job_count,
            'created_at': session.get('created_at')
        })
    finally:
        db.close()


# Add cleanup task
@app.before_request
def cleanup_old_sessions():
    """Cleanup old sessions periodically"""
    if not hasattr(app, 'last_cleanup'):
        app.last_cleanup = datetime.now()

    # Run cleanup once per day
    if datetime.now() - app.last_cleanup > timedelta(days=1):
        cleaned = session_manager.cleanup_old_sessions(days=7)
        print(f"Cleaned up {cleaned} old sessions")
        app.last_cleanup = datetime.now()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)