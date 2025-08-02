from flask import Flask, render_template, request, jsonify
from job_scraper import JobScraper  # Updated import
from models import Session, JobListing
import threading

app = Flask(__name__)

# Global variable to track scraping status
scraping_status = {'is_scraping': False, 'message': ''}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/scrape', methods=['POST'])
def scrape_jobs():
    global scraping_status

    if scraping_status['is_scraping']:
        return jsonify({'error': 'Scraping already in progress'}), 400

    data = request.json
    keyword = data.get('keyword', '').strip()
    sources = data.get('sources', [])

    if not keyword:
        return jsonify({'error': 'Keyword is required'}), 400

    if not sources:
        return jsonify({'error': 'At least one source must be selected'}), 400

    # Start scraping in background
    scraping_status['is_scraping'] = True
    scraping_status['message'] = 'Starting scraping...'

    def scrape_in_background():
        global scraping_status
        try:
            scraper = JobScraper()
            total_jobs = scraper.scrape_all(keyword, sources)
            scraping_status['message'] = f'Successfully scraped {total_jobs} jobs'
        except Exception as e:
            scraping_status['message'] = f'Error: {str(e)}'
        finally:
            scraping_status['is_scraping'] = False

    thread = threading.Thread(target=scrape_in_background)
    thread.start()

    return jsonify({'message': 'Scraping started'})


@app.route('/api/status')
def get_status():
    return jsonify(scraping_status)


@app.route('/api/jobs')
def get_jobs():
    session = Session()

    # Get filter parameters
    city = request.args.get('city', '')
    company = request.args.get('company', '')
    source = request.args.get('source', '')

    # Build query
    query = session.query(JobListing).filter_by(is_active=True)

    if city:
        query = query.filter(JobListing.city.contains(city))
    if company:
        query = query.filter(JobListing.company.contains(company))
    if source:
        query = query.filter_by(source=source)

    jobs = query.order_by(JobListing.created_at.desc()).all()

    # Convert to JSON
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

    session.close()
    return jsonify(jobs_data)


@app.route('/api/filters')
def get_filters():
    session = Session()

    # Get unique cities and companies
    cities = session.query(JobListing.city).filter_by(is_active=True).distinct().all()
    companies = session.query(JobListing.company).filter_by(is_active=True).distinct().all()

    cities_list = [city[0] for city in cities if city[0]]
    companies_list = [company[0] for company in companies if company[0]]

    session.close()
    return jsonify({
        'cities': sorted(cities_list),
        'companies': sorted(companies_list)
    })


# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)