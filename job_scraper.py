import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from models import Session, JobListing
from datetime import datetime
import urllib.parse


class JobScraper:
    def __init__(self):
        self.session = Session()

    def setup_selenium(self):
        """Setup Selenium WebDriver for dynamic content"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    # def setup_selenium(self):
    #     """Setup Selenium WebDriver for dynamic content"""
    #     options = Options()
    #     options.add_argument('--headless')
    #     options.add_argument('--no-sandbox')
    #     options.add_argument('--disable-dev-shm-usage')
    #     options.add_argument('--disable-gpu')
    #     options.add_argument('--disable-web-security')
    #     options.add_argument('--allow-running-insecure-content')
    #     options.add_argument('--disable-extensions')
    #     options.add_argument('--disable-plugins')
    #     options.add_argument('--disable-images')
    #     options.add_argument('--window-size=1920,1080')
    #     options.add_argument(
    #         'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    #
    #     # For Alpine Linux - use system chromium
    #     options.binary_location = '/usr/bin/chromium-browser'
    #
    #     try:
    #         # Use system chromedriver directly (no webdriver-manager in container)
    #         import os
    #         if os.path.exists('/usr/bin/chromedriver'):
    #             service = ChromeService('/usr/bin/chromedriver')
    #             driver = webdriver.Chrome(service=service, options=options)
    #             return driver
    #         else:
    #             # Fallback to webdriver-manager only if system driver not found
    #             service = ChromeService(ChromeDriverManager().install())
    #             driver = webdriver.Chrome(service=service, options=options)
    #             return driver
    #     except Exception as e:
    #         print(f"Error setting up Chrome driver: {e}")
    #         raise e



    def clear_previous_search(self, keyword):
        """Clear previous search results for the same keyword"""
        self.session.query(JobListing).filter_by(
            search_keyword=keyword,
            is_active=True
        ).update({'is_active': False})
        self.session.commit()

    def scrape_jobinja(self, keyword, max_results=30):
        """Scrape Jobinja website"""
        # Build URL with proper encoding
        encoded_keyword = urllib.parse.quote(keyword)
        base_url = f"https://jobinja.ir/jobs?filters%5Bkeywords%5D%5B%5D={encoded_keyword}"

        jobs = []
        page = 1

        while len(jobs) < max_results:
            url = f"{base_url}&page={page}" if page > 1 else base_url
            print(f"Scraping Jobinja page {page}: {url}")

            driver = None
            try:
                driver = self.setup_selenium()
                driver.get(url)
                time.sleep(5)  # Wait for JS to load

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Find job items with the correct class
                job_items = soup.find_all('li', class_='o-listView__item')
                if not job_items:
                    # Try alternative selector
                    job_items = soup.find_all('li', class_='c-jobListView__item')

                print(f"Found {len(job_items)} job items on page {page}")

                page_jobs = []
                for item in job_items:
                    try:
                        # Extract title and link
                        title_elem = item.find('h2', class_='o-listView__itemTitle')
                        if not title_elem:
                            title_elem = item.find('h2', class_='c-jobListView__title')

                        if title_elem:
                            title_link = title_elem.find('a')
                            if title_link:
                                title = title_link.text.strip()
                                link = title_link.get('href', '')
                                if not link.startswith('http'):
                                    link = f"https://jobinja.ir{link}"

                                # Extract company
                                company = ""
                                meta_items = item.find_all('li', class_='c-jobListView__metaItem')
                                for meta in meta_items:
                                    # Look for company icon
                                    if meta.find('i', class_='c-icon--construction'):
                                        company_span = meta.find('span')
                                        if company_span:
                                            company_text = company_span.text.strip()
                                            # Extract company name (before | if exists)
                                            if '|' in company_text:
                                                company = company_text.split('|')[0].strip()
                                            else:
                                                company = company_text

                                # Extract city
                                city = ""
                                for meta in meta_items:
                                    # Look for location icon
                                    if meta.find('i', class_='c-icon--place'):
                                        city_span = meta.find('span')
                                        if city_span:
                                            city = city_span.text.strip()
                                            # Clean up city text
                                            city = city.replace('\n', '').strip()

                                if title and link:
                                    page_jobs.append({
                                        'title': title,
                                        'company': company or 'نامشخص',
                                        'city': city or 'نامشخص',
                                        'link': link,
                                        'source': 'jobinja'
                                    })
                    except Exception as e:
                        print(f"Error parsing Jobinja item: {e}")
                        continue

                if not page_jobs:
                    print("No more jobs found, stopping pagination")
                    break

                jobs.extend(page_jobs[:max_results - len(jobs)])
                page += 1

                if len(jobs) >= max_results:
                    break

            except Exception as e:
                print(f"Error scraping Jobinja page {page}: {e}")
                break
            finally:
                if driver:
                    driver.quit()

            time.sleep(2)  # Delay between pages

        return jobs

    def scrape_jobvision(self, keyword, max_results=30):
        """Scrape Jobvision website"""
        # Build URL with proper encoding
        encoded_keyword = urllib.parse.quote(keyword)
        base_url = f"https://jobvision.ir/jobs/keyword/{encoded_keyword}"

        jobs = []
        page = 1

        while len(jobs) < max_results:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            print(f"Scraping Jobvision page {page}: {url}")

            driver = None
            try:
                driver = self.setup_selenium()
                driver.get(url)

                # Wait for job cards to load
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "job-card")))
                time.sleep(3)  # Additional wait for all cards to load

                # Scroll to load more jobs
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                # Find job cards
                job_items = soup.find_all('job-card')
                print(f"Found {len(job_items)} job items on page {page}")

                page_jobs = []
                for item in job_items:
                    try:
                        # Extract title
                        title_elem = item.find('div', class_='job-card-title')
                        title = title_elem.text.strip() if title_elem else ""

                        # Extract link
                        link_elem = item.find('a', href=True)
                        link = link_elem.get('href', '') if link_elem else ""
                        if link and not link.startswith('http'):
                            link = f"https://jobvision.ir{link}"

                        # Extract company
                        company = ""
                        company_elem = item.find('a', href=lambda h: h and '/companies/' in h if h else False)
                        if company_elem:
                            company = company_elem.text.strip()

                        # Extract city
                        city = ""
                        city_elem = item.find('span', class_='text-secondary')
                        if city_elem:
                            city_text = city_elem.text.strip()
                            # Extract city name (before ، if exists)
                            if '،' in city_text:
                                city = city_text.split('،')[0].strip()
                            else:
                                city = city_text

                        if title and link:
                            page_jobs.append({
                                'title': title,
                                'company': company or 'نامشخص',
                                'city': city or 'نامشخص',
                                'link': link,
                                'source': 'jobvision'
                            })
                    except Exception as e:
                        print(f"Error parsing Jobvision item: {e}")
                        continue

                if not page_jobs:
                    print("No more jobs found, stopping pagination")
                    break

                jobs.extend(page_jobs[:max_results - len(jobs)])
                page += 1

                if len(jobs) >= max_results:
                    break

            except Exception as e:
                print(f"Error scraping Jobvision page {page}: {e}")
                break
            finally:
                if driver:
                    driver.quit()

            time.sleep(2)  # Delay between pages

        return jobs

    def scrape_irantalent(self, keyword, max_results=30):
        """Alternative IranTalent scraper with different approach"""
        jobs = []
        base_url = "https://www.irantalent.com"

        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            search_url = f"{base_url}/jobs/{keyword}"
            driver = self.setup_selenium()
            driver.get(search_url)

            # Wait for specific elements
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "card-wrapper"))
                )
                print("Job cards loaded!")
            except:
                print("Timeout waiting for job cards")

            # Additional wait
            time.sleep(3)

            # Execute JavaScript to get job data directly
            job_data_script = """
            var jobs = [];
            var cards = document.querySelectorAll('div.card-wrapper');

            cards.forEach(function(card) {
                var link = card.querySelector('a.position');
                var title = card.querySelector('p.position-title');
                var company = card.querySelector('p.color-light-black');
                var location = card.querySelector('span.location');
                var salaryDiv = card.querySelector('div.salary span');
                var dateSpans = card.querySelectorAll('span.color-gray');

                if (link && title) {
                    var dateText = '';
                    dateSpans.forEach(function(span) {
                        if (span.textContent.includes('روز پیش') || 
                            span.textContent.includes('ساعت پیش') ||
                            span.textContent.includes('هفته پیش')) {
                            dateText = span.textContent.trim();
                        }
                    });

                    jobs.push({
                        link: link.getAttribute('href'),
                        title: title.textContent.trim(),
                        company: company ? company.textContent.trim() : 'نامشخص',
                        location: location ? location.textContent.trim() : 'تهران',
                        salary: salaryDiv ? salaryDiv.textContent.trim() : '',
                        date: dateText
                    });
                }
            });

            return jobs;
            """

            # Execute script to get jobs
            js_jobs = driver.execute_script(job_data_script)

            print(f"Found {len(js_jobs)} jobs via JavaScript")

            # Process JavaScript results
            for js_job in js_jobs[:max_results]:
                job_link = js_job['link']
                if job_link.startswith('/'):
                    job_link = base_url + job_link

                job_data = {
                    'title': js_job['title'],
                    'company': js_job['company'],
                    # 'location': js_job['location'],
                    'city': js_job['location'],  # Changed from 'location' to 'city'
                    'link': job_link,
                    'salary': js_job['salary'],
                    'date': js_job['date'],
                    'source': 'irantalent'
                }

                jobs.append(job_data)
                print(f"Added: {js_job['title']} at {js_job['company']}")

            driver.quit()

        except Exception as e:
            print(f"Error in alternative scraper: {e}")
            import traceback
            traceback.print_exc()

        return jobs

    def debug_irantalent(self, keyword):
        """Debug function to see what's on the page"""
        try:
            driver = self.setup_selenium()
            url = f"https://www.irantalent.com/jobs/{keyword}"
            driver.get(url)

            print("Waiting for page load...")
            time.sleep(10)

            # Check various elements
            checks = [
                ('div.card-wrapper', 'Card wrappers'),
                ('new-position-card', 'Position cards'),
                ('a.position', 'Position links'),
                ('p.position-title', 'Position titles'),
                ('a[href*="/job/"]', 'Job links'),
                ('.ng-star-inserted', 'Angular elements')
            ]

            for selector, name in checks:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"{name}: {len(elements)} found")

            # Save screenshot
            driver.save_screenshot('irantalent_debug.png')
            print("Screenshot saved as irantalent_debug.png")

            # Save full HTML
            with open('irantalent_full_debug.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("Full HTML saved as irantalent_full_debug.html")

            driver.quit()

        except Exception as e:
            print(f"Debug error: {e}")

    def save_jobs(self, jobs, keyword):
        """Save jobs to database"""
        saved_count = 0
        for job in jobs:
            try:
                # Check if job already exists (by link)
                existing = self.session.query(JobListing).filter_by(
                    link=job['link'],
                    search_keyword=keyword
                ).first()

                if not existing:
                    job_listing = JobListing(
                        title=job['title'],
                        company=job['company'],
                        city=job['city'],
                        link=job['link'],
                        source=job['source'],
                        search_keyword=keyword,
                        is_active=True
                    )
                    self.session.add(job_listing)
                    saved_count += 1
            except Exception as e:
                print(f"Error saving job: {e}")
                continue

        self.session.commit()
        print(f"Saved {saved_count} new jobs to database")



    def scrape_all(self, keyword, sources, max_results_per_site=30):
        """Scrape all selected sources"""
        # Clear previous results for this keyword
        self.clear_previous_search(keyword)

        all_jobs = []

        if 'jobinja' in sources:
            print("Scraping Jobinja...")
            try:
                jobinja_jobs = self.scrape_jobinja(keyword, max_results_per_site)
                all_jobs.extend(jobinja_jobs)
                print(f"Found {len(jobinja_jobs)} jobs on Jobinja")
            except Exception as e:
                print(f"Error scraping Jobinja: {e}")

        if 'jobvision' in sources:
            print("Scraping Jobvision...")
            try:
                jobvision_jobs = self.scrape_jobvision(keyword, max_results_per_site)
                all_jobs.extend(jobvision_jobs)
                print(f"Found {len(jobvision_jobs)} jobs on Jobvision")
            except Exception as e:
                print(f"Error scraping Jobvision: {e}")

        if 'irantalent' in sources:
            print("Scraping irantalent...")
            try:
                irantalent_jobs = self.scrape_irantalent(keyword, max_results_per_site)
                all_jobs.extend(irantalent_jobs)
                print(f"Found {len(irantalent_jobs)} jobs on irantalent")
            except Exception as e:
                print(f"Error scraping irantalent: {e}")

        # Save to database
        if all_jobs:
            self.save_jobs(all_jobs, keyword)

        return len(all_jobs)