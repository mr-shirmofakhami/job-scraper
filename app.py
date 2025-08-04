from flask import Flask, render_template, request, jsonify, session
from flask_session import Session as FlaskSession
import uuid
import os
from datetime import datetime, timedelta
from job_scraper import JobScraper
from session_manager import SessionManager
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

# Global variables for scraping status
scraping_status = {
    'is_scraping': False,
    'message': 'Ready',
    'progress': 0
}

# Initialize components
session_manager = SessionManager(DBSession)
job_scraper = JobScraper(session_manager)  # Pass session_manager to JobScraper

@app.route('/')
def index():
    # Get or create session
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['created_at'] = datetime.now().isoformat()

    session_id = session_manager.get_or_create_session(session['session_id'])
    return render_template('index.html', session_id=session_id)


@app.route('/api/scrape', methods=['POST'])
def start_scraping():
    global scraping_status

    if scraping_status['is_scraping']:
        return jsonify({'error': 'Scraping already in progress'}), 400

    data = request.json
    keyword = data.get('keyword', '')
    sources = data.get('sources', [])

    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400

    if not sources:
        return jsonify({'error': 'At least one source is required'}), 400

    # Get or create session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']

    # Start scraping in background thread
    thread = threading.Thread(
        target=scrape_background,
        args=(keyword, sources, session_id)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Scraping started', 'session_id': session_id})

def scrape_background(keyword, sources, session_id):
    global scraping_status

    try:
        scraping_status = {
            'is_scraping': True,
            'message': 'Starting scrape...',
            'progress': 0
        }

        # Clear previous results for this session
        session_manager.clear_session_jobs(session_id)

        scraping_status['message'] = 'Scraping jobs...'
        scraping_status['progress'] = 20

        # Scrape jobs
        total_jobs = job_scraper.scrape_all(keyword, sources, session_id=session_id)

        scraping_status = {
            'is_scraping': False,
            'message': f'Successfully found {total_jobs} jobs',
            'progress': 100
        }

    except Exception as e:
        scraping_status = {
            'is_scraping': False,
            'message': f'Error: {str(e)}',
            'progress': 0
        }


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
    sort_by = request.args.get('sort', 'newest')

    # Get jobs for this session
    jobs = session_manager.get_session_jobs(session_id, source, city, company, sort_by)

    return jsonify(jobs)


@app.route('/api/filters')
def get_filters():
    # Get session ID
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'cities': [], 'companies': []})

    # Get unique cities and companies for this session
    jobs = session_manager.get_session_jobs(session_id)

    cities = list(set(job['city'] for job in jobs if job['city']))
    companies = list(set(job['company'] for job in jobs if job['company']))

    cities.sort()
    companies.sort()

    return jsonify({
        'cities': cities,
        'companies': companies
    })


@app.route('/api/clear-session', methods=['POST'])
def clear_session():
    """Clear current session's jobs"""
    session_id = session.get('session_id')
    if session_id:
        session_manager.clear_session_jobs(session_id)

    return jsonify({'message': 'نتایج پاک شد', 'session_id': session_id})



@app.route('/api/session-info')
def session_info():
    session_id = session.get('session_id')
    if not session_id:
        session['session_id'] = str(uuid.uuid4())
        session_id = session['session_id']

    jobs = session_manager.get_session_jobs(session_id)

    return jsonify({
        'session_id': session_id,
        'job_count': len(jobs)
    })


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


# Add this route temporarily for testing
@app.route('/test-irantalent')
def test_irantalent():
    scraper = JobScraper()
    scraper.test_irantalent_simple('python')
    return "Check console output and generated files"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)