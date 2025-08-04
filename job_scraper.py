import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
from session_manager import SessionManager
from models import Session as DBSession, JobListing


class JobScraper:
    def __init__(self, session_manager=None):
        """Initialize JobScraper with optional session_manager"""
        if session_manager is None:
            # Create a new SessionManager with DBSession
            self.session_manager = SessionManager(DBSession)
        else:
            self.session_manager = session_manager

    def setup_selenium(self):
        """Setup Chrome driver with headless options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        return driver

    # def scrape_all(self, keyword, sources, session_id):
    #     """Scrape jobs from multiple sources"""
    #     total_jobs = 0
    #     all_jobs = []
    #
    #     print(f"Starting scrape for keyword: {keyword}")
    #     print(f"Sources: {sources}")
    #
    #     for source in sources:
    #         print(f"\n--- Scraping {source} ---")
    #         jobs = []
    #
    #         try:
    #             if source == 'jobinja':
    #                 jobs = self.scrape_jobinja(keyword)
    #             elif source == 'jobvision':
    #                 jobs = self.scrape_jobvision(keyword)
    #             elif source == 'irantalent':
    #                 jobs = self.scrape_irantalent(keyword)
    #
    #             print(f"Found {len(jobs)} jobs from {source}")
    #             all_jobs.extend(jobs)
    #
    #         except Exception as e:
    #             print(f"Error scraping {source}: {e}")
    #             continue
    #
    #     # Save all jobs to session
    #     if all_jobs:
    #         saved_count = self.session_manager.save_session_jobs(session_id, all_jobs, keyword)
    #         total_jobs = saved_count
    #
    #     print(f"\nTotal jobs found and saved: {total_jobs}")
    #     return total_jobs

    def scrape_jobinja(self, keyword, max_results=30):
        """Scrape jobs from Jobinja with date extraction"""
        jobs = []
        base_url = "https://jobinja.ir"

        try:
            driver = self.setup_selenium()

            search_url = f"{base_url}/jobs?filters%5Bkeywords%5D%5B%5D={keyword}&page=1"
            driver.get(search_url)

            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "c-jobListView__title")))

            time.sleep(3)

            job_cards = driver.find_elements(By.CSS_SELECTOR, "li.c-jobListView__item")
            print(f"Found {len(job_cards)} job cards on Jobinja")

            for card in job_cards[:max_results]:
                try:
                    # Extract title and date together
                    title_elem = card.find_element(By.CSS_SELECTOR, "h2.c-jobListView__title")
                    title_link = title_elem.find_element(By.CSS_SELECTOR, "a.c-jobListView__titleLink")
                    title = title_link.text.strip()
                    link = title_link.get_attribute("href")

                    # Extract date from the span
                    date = ""
                    try:
                        date_span = title_elem.find_element(By.CSS_SELECTOR, "span.c-jobListView__passedDays")
                        date_text = date_span.text.strip()
                        # Remove parentheses
                        date = date_text.replace('(', '').replace(')', '').strip()
                    except:
                        pass

                    # # Extract company
                    # company = "نامشخص"
                    # try:
                    #     company_elem = card.find_element(By.CSS_SELECTOR, "span.c-jobListView__company")
                    #     company = company_elem.text.strip()
                    # except:
                    #     pass
                    #
                    # # Extract location
                    # location = "تهران"
                    # try:
                    #     location_elem = card.find_element(By.CSS_SELECTOR, "span.c-jobListView__locationText")
                    #     location = location_elem.text.strip()
                    # except:
                    #     pass

                    # Extract company (first <li> > <span> inside the <ul>)
                    company = "نامشخص"
                    try:
                        # Selector: Targets the <span> in the first <li> of the <ul>
                        company_elem = card.find_element(By.CSS_SELECTOR,
                                                         "ul.o-listView__itemComplementInfo > li:first-child > span")
                        company = company_elem.text.strip()  # Strips extra spaces; result: "تجارت الکترونیک پارسیان | Parsian E-commerce"
                    except:
                        pass  # Or log an error: print("Company not found")

                    # Extract location/city (second <li> > <span> inside the <ul>)
                    location = "unknown"
                    try:
                        # Selector: Targets the <span> in the second <li> of the <ul>
                        location_elem = card.find_element(By.CSS_SELECTOR,
                                                          "ul.o-listView__itemComplementInfo > li:nth-child(2) > span")
                        location = location_elem.text.strip()  # Strips extra spaces; result: "تهران، تهران"
                    except:
                        pass  # Or log an error: print("Location not found")

                    job_data = {
                        'title': title,
                        'company': company,
                        'location': location,
                        'link': link,
                        'date': date,
                        'source': 'jobinja'
                    }

                    jobs.append(job_data)
                    print(f"Found: {title} at {company} - {date}")

                except Exception as e:
                    print(f"Error extracting job from card: {e}")
                    continue

            driver.quit()

        except Exception as e:
            print(f"Error scraping Jobinja: {e}")
            import traceback
            traceback.print_exc()

        return jobs

    def scrape_jobvision(self, keyword, max_results=30):
        """Fixed Jobvision scraper with proper date extraction"""
        jobs = []
        base_url = "https://jobvision.ir"

        try:
            search_url = f"{base_url}/jobs/keyword/{keyword}"
            print(f"Scraping Jobvision: {search_url}")

            driver = self.setup_selenium()
            driver.get(search_url)

            print("Waiting for page to load...")
            try:
                wait = WebDriverWait(driver, 20)
                wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "job-card"))
                )
                print("Job cards detected!")
            except:
                print("Timeout waiting for job cards")

            time.sleep(3)
            driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(2)

            job_elements = driver.find_elements(By.TAG_NAME, "job-card")
            print(f"Found {len(job_elements)} job elements")

            for element in job_elements[:max_results]:
                try:
                    # Find the job link within the job-card
                    job_link = element.find_element(By.CSS_SELECTOR, 'a[href*="/jobs/"]')
                    href = job_link.get_attribute('href')
                    if not href or '/jobs/' not in href:
                        continue

                    # Make sure we have full URL
                    if not href.startswith('http'):
                        href = base_url + href

                    card = element

                    title = "نامشخص"
                    company = "نامشخص"
                    date = ""

                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, '.job-card-title')
                        title = title_elem.text.strip()
                    except:
                        pass

                    try:
                        company_elem = card.find_element(By.CSS_SELECTOR, 'a[href*="/companies/"]')
                        company = company_elem.text.strip()
                    except:
                        pass

                    # Extract location and date
                    location = "unknown"
                    try:
                        # Target the container <div> with stable classes
                        location_div = card.find_element(By.CSS_SELECTOR,
                                                         'div.d-flex.flex-wrap.align-items-center.text-secondary.line-height-24')

                        # Get the first <span> inside it (which contains the location text)
                        location_span = location_div.find_element(By.CSS_SELECTOR,
                                                                  'span.text-secondary.pointer-events-none.ng-star-inserted')

                        # Extract and clean the text (e.g., "اصفهان ، مارنان")
                        full_location = location_span.text.strip()

                        # Split by Persian comma to get just the city (first part), e.g., "اصفهان"
                        if '،' in full_location:
                            location = full_location.split('،')[0].strip()
                        else:
                            location = full_location  # Fallback if no comma
                    except Exception as e:
                        # Optional: Log the error for debugging (e.g., if structure changes)
                        print(f"Error extracting location: {e}")
                        pass

                    try:
                        # Look for date in spans with gray color
                        date_elements = card.find_elements(By.CSS_SELECTOR, 'span[style*="color: #8E9CB2"]')
                        for elem in date_elements:
                            text = elem.text.strip()
                            if any(word in text for word in
                                   ['روز پیش', 'ساعت پیش', 'هفته پیش', 'ماه پیش', 'دیروز', 'امروز']):
                                date = text
                                break

                        # Alternative: look in all spans if not found
                        if not date:
                            all_spans = card.find_elements(By.TAG_NAME, "span")
                            for span in all_spans:
                                text = span.text.strip()
                                if any(word in text for word in
                                       ['روز پیش', 'ساعت پیش', 'هفته پیش', 'ماه پیش', 'دیروز', 'امروز']):
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
                            'date': date,
                            'source': 'jobvision'
                        }
                        jobs.append(job_data)
                        print(f"Found: {title} at {company} - {date}")

                except Exception as e:
                    print(f"Error extracting job: {e}")
                    continue

            driver.quit()

        except Exception as e:
            print(f"Jobvision scraper error: {e}")
            import traceback
            traceback.print_exc()

        return jobs

    def scrape_irantalent(self, keyword, max_results=30):
        """Fixed IranTalent scraper with proper date extraction"""
        jobs = []
        base_url = "https://www.irantalent.com"

        try:
            # Check if keyword contains multiple words
            if ' ' in keyword.strip():
                # Multiple words - use search format with dashes
                keyword_formatted = keyword.strip().replace(' ', '-')
                search_url = f"{base_url}/jobs/search?keyword={keyword_formatted}&language=persian"
            else:
                # Single word - use simple format
                search_url = f"{base_url}/jobs/{keyword}"

            print(f"Scraping IranTalent: {search_url}")

            driver = self.setup_selenium()
            driver.get(search_url)

            print("Waiting for page to load...")
            try:
                wait = WebDriverWait(driver, 20)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/job/"]'))
                )
                print("Job elements detected!")
            except:
                print("Timeout waiting for job elements")

            time.sleep(3)
            driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(2)

            job_elements = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/job/"]')
            print(f"Found {len(job_elements)} job elements")

            for element in job_elements[:max_results]:
                try:
                    href = element.get_attribute('href')
                    if not href or '/job/' not in href:
                        continue

                    card = element
                    for _ in range(5):
                        parent = card.find_element(By.XPATH, '..')
                        if 'card' in parent.get_attribute('class') or 'position' in parent.get_attribute('class'):
                            card = parent
                            break
                        card = parent

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

                    # Extract location and date from job-info div
                    try:
                        job_info = card.find_element(By.CSS_SELECTOR, 'div.job-info')
                        spans = job_info.find_elements(By.CSS_SELECTOR, 'span.color-gray')

                        if len(spans) >= 1:
                            location = spans[0].text.strip()

                        # The date is usually the last span with "روز پیش" or similar
                        for span in reversed(spans):
                            text = span.text.strip()
                            if any(word in text for word in
                                   ['روز پیش', 'ساعت پیش', 'هفته پیش', 'ماه پیش', 'دیروز', 'امروز']):
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
                        print(f"Found: {title} at {company} - {date}")

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
