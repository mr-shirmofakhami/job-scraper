from job_scraper import JobScraper

# Test the scraper
scraper = JobScraper()

# Test Jobinja
print("Testing Jobinja...")
jobinja_results = scraper.scrape_jobinja("dba", max_results=5)
print(f"Found {len(jobinja_results)} jobs on Jobinja")
for job in jobinja_results[:3]:
    print(f"- {job['title']} at {job['company']} in {job['city']}")

print("\n" + "="*50 + "\n")

# Test Jobvision
print("Testing Jobvision...")
jobvision_results = scraper.scrape_jobvision("dba", max_results=5)
print(f"Found {len(jobvision_results)} jobs on Jobvision")
for job in jobvision_results[:3]:
    print(f"- {job['title']} at {job['company']} in {job['city']}")