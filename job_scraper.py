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
from models import Session as DBSession, JobListing
from session_manager import SessionJobManager
from datetime import datetime


class JobScraper:
    def __init__(self, session_manager=None):
        self.session_manager = session_manager or SessionJobManager()
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
        """Fixed IranTalent scraper using the working URL format"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        jobs = []
        base_url = "https://www.irantalent.com"

        try:
            # Use the working URL format
            search_url = f"{base_url}/jobs?q={keyword}"
            print(f"Scraping IranTalent: {search_url}")

            driver = self.setup_selenium()
            driver.get(search_url)

            # Wait for Angular to initialize
            print("Waiting for page to load...")
            try:
                wait = WebDriverWait(driver, 20)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/job/"]'))
                )
                print("Job elements detected!")
            except:
                print("Timeout waiting for job elements")

            # Additional wait for all elements to load
            time.sleep(3)

            # Scroll to load more if needed
            driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(2)

            # Find job elements
            job_elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/job/"]')
            print(f"Found {len(job_elements)} job elements")

            # Extract jobs
            for element in job_elements[:max_results]:
                try:
                    href = element.get_attribute('href')
                    if not href or '/job/' not in href:
                        continue

                    # Find the parent card
                    card = element
                    for _ in range(5):
                        parent = card.find_element(By.XPATH, '..')
                        if 'card' in parent.get_attribute('class') or 'position' in parent.get_attribute('class'):
                            card = parent
                            break
                        card = parent

                    # Extract data
                    title = "نامشخص"
                    company = "نامشخص"
                    location = "تهران"
                    salary = ""
                    date = ""

                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, 'p.position-title, .position-title')
                        title = title_elem.text.strip()
                    except:
                        pass

                    try:
                        company_elem = card.find_element(By.CSS_SELECTOR, 'p.color-light-black')
                        company = company_elem.text.strip()
                    except:
                        pass

                    try:
                        location_elem = card.find_element(By.CSS_SELECTOR, 'span.location')
                        location = location_elem.text.strip()
                    except:
                        pass

                    try:
                        salary_elem = card.find_element(By.CSS_SELECTOR, '.salary span')
                        salary = salary_elem.text.strip()
                    except:
                        pass

                    # Extract date
                    try:
                        date_elems = card.find_elements(By.CSS_SELECTOR, 'span.color-gray')
                        for elem in date_elems:
                            text = elem.text.strip()
                            if any(word in text for word in ['روز پیش', 'ساعت پیش', 'هفته پیش', 'ماه پیش']):
                                date = text
                                break
                    except:
                        pass

                    if title != "نامشخص":
                        job_data = {
                            'title': title,
                            'company': company,
                            'location': location,
                            'link': href,
                            'salary': salary,
                            'date': date,
                            'source': 'irantalent'
                        }
                        jobs.append(job_data)
                        print(f"Found: {title} at {company}")

                except Exception as e:
                    print(f"Error extracting job: {e}")
                    continue

            driver.quit()

        except Exception as e:
            print(f"IranTalent scraper error: {e}")
            import traceback
            traceback.print_exc()

        return jobs

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

    def save_jobs(self, jobs, search_keyword, session_id=None):
        """Save jobs to database using SQLAlchemy"""
        if session_id and self.session_manager:
            return self.session_manager.save_session_jobs(session_id, jobs, search_keyword)
        else:
            # Fallback to regular save without session
            db = DBSession()
            saved_count = 0

            try:
                for job in jobs:
                    try:
                        city_value = job.get('city') or job.get('location') or 'نامشخص'

                        existing = db.query(JobListing).filter_by(link=job.get('link', '')).first()

                        if not existing:
                            job_listing = JobListing(
                                title=job.get('title', 'نامشخص'),
                                company=job.get('company', 'نامشخص'),
                                city=city_value,
                                link=job.get('link', ''),
                                source=job.get('source', ''),
                                search_keyword=search_keyword
                            )
                            db.add(job_listing)
                            saved_count += 1

                    except Exception as e:
                        print(f"Error saving job: {e}")
                        continue

                db.commit()
            finally:
                db.close()

            return saved_count

    def scrape_all(self, keyword, sources, max_results_per_site=30, session_id=None):
        """Scrape all selected sources"""
        # Clear previous results for this session if session_id provided
        if session_id and self.session_manager:
            self.session_manager.clear_session_jobs(session_id)

        all_jobs = []

        if 'jobinja' in sources:
            print("Scraping Jobinja...")
            try:
                jobinja_jobs = self.scrape_jobinja(keyword, max_results_per_site)
                all_jobs.extend(jobinja_jobs)
                print(f"✅ Found {len(jobinja_jobs)} jobs on Jobinja")
            except Exception as e:
                print(f"❌ Error scraping Jobinja: {e}")

        if 'jobvision' in sources:
            print("Scraping Jobvision...")
            try:
                jobvision_jobs = self.scrape_jobvision(keyword, max_results_per_site)
                all_jobs.extend(jobvision_jobs)
                print(f"✅ Found {len(jobvision_jobs)} jobs on Jobvision")
            except Exception as e:
                print(f"❌ Error scraping Jobvision: {e}")

        if 'irantalent' in sources:
            print("Scraping IranTalent...")
            try:
                irantalent_jobs = self.scrape_irantalent(keyword, max_results_per_site)
                all_jobs.extend(irantalent_jobs)
                print(f"✅ Found {len(irantalent_jobs)} jobs on IranTalent")
            except Exception as e:
                print(f"❌ Error scraping IranTalent: {e}")

        # Save to database
        if all_jobs:
            saved = self.save_jobs(all_jobs, keyword, session_id)
            print(f"💾 Total jobs found: {len(all_jobs)}, Successfully saved: {saved}")
        else:
            print("⚠️ No jobs found from any source")

        return len(all_jobs)
