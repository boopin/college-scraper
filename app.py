import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re
from urllib.parse import urljoin
from typing import List, Dict, Optional
import concurrent.futures
import threading
from queue import Queue
import asyncio
import aiohttp
import random

# Page config
st.set_page_config(
    page_title="Efficient College Scraper",
    page_icon="⚡",
    layout="wide"
)

class EfficientCollegeScraper:
    def __init__(self):
        self.session = requests.Session()
        # Rotate user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.update_headers()
        
        # Rate limiting
        self.request_lock = threading.Lock()
        self.last_request_time = {}
        self.min_delay = 1.0
        
        # Results storage
        self.results_queue = Queue()
        self.error_queue = Queue()
    
    def update_headers(self):
        """Rotate user agent and headers"""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
    
    def rate_limited_request(self, url: str, delay: float = None) -> Optional[BeautifulSoup]:
        """Rate-limited request with automatic retry"""
        if delay is None:
            delay = self.min_delay
        
        domain = url.split('/')[2]
        
        with self.request_lock:
            # Check if we need to wait
            if domain in self.last_request_time:
                time_since_last = time.time() - self.last_request_time[domain]
                if time_since_last < delay:
                    time.sleep(delay - time_since_last)
            
            self.last_request_time[domain] = time.time()
        
        # Retry logic
        for attempt in range(3):
            try:
                # Rotate headers for each request
                if attempt > 0:
                    self.update_headers()
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
                
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                if len(response.content) < 1000:
                    raise Exception(f"Response too small: {len(response.content)} bytes")
                
                return BeautifulSoup(response.content, 'html.parser')
                
            except Exception as e:
                if attempt == 2:  # Last attempt
                    self.error_queue.put(f"Failed to fetch {url}: {str(e)}")
                    return None
                continue
        
        return None
    
    def scrape_college_urls_batch(self, ranking_urls: List[str], max_colleges_per_url: int = 20) -> List[str]:
        """Extract college URLs from multiple ranking pages in parallel"""
        college_urls = []
        
        def scrape_single_ranking_page(url):
            soup = self.rate_limited_request(url)
            if not soup:
                return []
            
            # Find college links
            college_links = []
            university_links = soup.find_all('a', href=True)
            
            for link in university_links:
                href = link.get('href', '')
                if 'university' in href and 'careers360.com' in href:
                    full_url = urljoin(url, href)
                    if full_url not in college_links:
                        college_links.append(full_url)
                        if len(college_links) >= max_colleges_per_url:
                            break
            
            return college_links
        
        # Parallel processing of ranking pages
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(scrape_single_ranking_page, url): url for url in ranking_urls}
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_colleges = future.result()
                    college_urls.extend(page_colleges)
                    st.success(f"✅ Found {len(page_colleges)} colleges from {url}")
                except Exception as e:
                    st.error(f"❌ Error scraping {url}: {str(e)}")
        
        return list(set(college_urls))  # Remove duplicates
    
    def scrape_college_parallel(self, college_url: str, include_courses: bool = True, 
                              include_admissions: bool = True, include_placements: bool = True) -> Dict:
        """Scrape a single college's all pages in parallel"""
        base_url = college_url.rstrip('/')
        urls_to_scrape = {'main': base_url}
        
        if include_courses:
            urls_to_scrape['courses'] = f"{base_url}/courses"
        if include_admissions:
            urls_to_scrape['admissions'] = f"{base_url}/admission"
        if include_placements:
            urls_to_scrape['placements'] = f"{base_url}/placement"
        
        college_data = {
            'url': college_url,
            'name': 'Unknown',
            'scraped_sections': []
        }
        
        def scrape_section(section_name, url):
            soup = self.rate_limited_request(url, delay=random.uniform(1.0, 2.0))
            if not soup:
                return section_name, None
            
            if section_name == 'main':
                return section_name, self.extract_overview_data(soup)
            elif section_name == 'courses':
                return section_name, self.extract_courses_data(soup)
            elif section_name == 'admissions':
                return section_name, self.extract_admissions_data(soup)
            elif section_name == 'placements':
                return section_name, self.extract_placements_data(soup)
            
            return section_name, None
        
        # Parallel scraping of all sections
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_section = {
                executor.submit(scrape_section, section, url): section 
                for section, url in urls_to_scrape.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_section):
                section = future_to_section[future]
                try:
                    section_name, data = future.result()
                    if data:
                        college_data[section_name] = data
                        college_data['scraped_sections'].append(section_name)
                except Exception as e:
                    self.error_queue.put(f"Error scraping {section} for {college_url}: {str(e)}")
        
        # Extract college name from main page data
        if 'main' in college_data:
            college_data['name'] = college_data['main'].get('name', 'Unknown')
        
        return college_data
    
    def batch_scrape_colleges(self, college_urls: List[str], max_workers: int = 5, 
                            include_courses: bool = True, include_admissions: bool = True, 
                            include_placements: bool = True) -> List[Dict]:
        """Scrape multiple colleges in parallel with progress tracking"""
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def scrape_single_college(college_url):
            return self.scrape_college_parallel(
                college_url, include_courses, include_admissions, include_placements
            )
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(scrape_single_college, url): url 
                for url in college_urls
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    college_data = future.result()
                    results.append(college_data)
                    completed += 1
                    
                    progress = completed / len(college_urls)
                    progress_bar.progress(progress)
                    status_text.text(f"✅ Completed {completed}/{len(college_urls)}: {college_data['name']}")
                    
                except Exception as e:
                    self.error_queue.put(f"Error scraping {url}: {str(e)}")
                    completed += 1
                    progress_bar.progress(completed / len(college_urls))
        
        return results
    
    def extract_overview_data(self, soup: BeautifulSoup) -> Dict:
        """Extract college overview data"""
        data = {
            'name': 'Unknown',
            'location': 'N/A',
            'established': 'N/A',
            'type': 'N/A'
        }
        
        # Extract name
        name_elements = soup.select('h1, .college-name, .university-name, .main-heading')
        for element in name_elements:
            name = element.get_text(strip=True)
            if len(name) > 5 and 'careers360' not in name.lower():
                data['name'] = name
                break
        
        page_text = soup.get_text()
        
        # Extract establishment year
        year_match = re.search(r'(?:established|founded).*?(\d{4})', page_text, re.IGNORECASE)
        if year_match:
            data['established'] = year_match.group(1)
        
        # Extract location
        location_patterns = [
            r'([A-Z][a-z]+,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'(?:located in|address).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, page_text)
            if match:
                data['location'] = match.group(1)
                break
        
        return data
    
    def extract_courses_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract courses data efficiently"""
        courses = []
        
        # Look for tables first (most structured)
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    course_name = None
                    
                    # Find course name
                    for text in cell_texts:
                        if any(keyword in text.lower() for keyword in ['tech', 'mba', 'mca', 'msc']):
                            if len(text) > 5:
                                course_name = text
                                break
                    
                    if course_name:
                        all_text = ' '.join(cell_texts)
                        courses.append({
                            'name': course_name,
                            'fees': self.extract_fees(all_text),
                            'duration': self.extract_duration(all_text),
                            'seats': self.extract_seats(all_text)
                        })
        
        return courses[:20]  # Limit to avoid too much data
    
    def extract_admissions_data(self, soup: BeautifulSoup) -> Dict:
        """Extract admissions data efficiently"""
        page_text = soup.get_text()
        
        # Extract entrance exams
        exam_keywords = ['JEE', 'GATE', 'CAT', 'MAT', 'NEET', 'JAM', 'CLAT']
        entrance_exams = [exam for exam in exam_keywords if exam.lower() in page_text.lower()]
        
        # Extract application fee
        fee_match = re.search(r'application\s+fee[:\s]*₹\s*[\d,]+', page_text, re.IGNORECASE)
        application_fee = fee_match.group(0) if fee_match else 'N/A'
        
        return {
            'entrance_exams': entrance_exams,
            'application_fee': application_fee
        }
    
    def extract_placements_data(self, soup: BeautifulSoup) -> Dict:
        """Extract placements data efficiently"""
        page_text = soup.get_text()
        
        # Extract placement rate
        rate_match = re.search(r'(\d+(?:\.\d+)?)%.*?(?:placement|placed)', page_text, re.IGNORECASE)
        placement_rate = f"{rate_match.group(1)}%" if rate_match else 'N/A'
        
        # Extract average package
        package_match = re.search(r'average.*?package.*?₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)', page_text, re.IGNORECASE)
        average_package = f"₹{package_match.group(1)} LPA" if package_match else 'N/A'
        
        # Extract top recruiters
        recruiter_keywords = ['Microsoft', 'Google', 'Amazon', 'TCS', 'Infosys', 'Goldman Sachs']
        top_recruiters = [company for company in recruiter_keywords if company.lower() in page_text.lower()]
        
        return {
            'placement_rate': placement_rate,
            'average_package': average_package,
            'top_recruiters': top_recruiters
        }
    
    def extract_fees(self, text: str) -> str:
        """Extract fees efficiently"""
        pattern = r'₹\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|L))?'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else 'N/A'
    
    def extract_duration(self, text: str) -> str:
        """Extract duration efficiently"""
        pattern = r'(\d+)\s*(?:year|yr)s?'
        match = re.search(pattern, text, re.IGNORECASE)
        return f"{match.group(1)} Years" if match else 'N/A'
    
    def extract_seats(self, text: str) -> str:
        """Extract seats efficiently"""
        pattern = r'(\d+)\s*(?:seat|intake)'
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else 'N/A'

def main():
    st.title("⚡ Efficient Multi-threaded College Scraper")
    st.markdown("**Parallel processing for faster, more reliable scraping**")
    
    # Initialize
    if 'efficient_scraper' not in st.session_state:
        st.session_state.efficient_scraper = EfficientCollegeScraper()
    if 'scraped_colleges' not in st.session_state:
        st.session_state.scraped_colleges = []
    
    with st.sidebar:
        st.header("⚙️ Efficient Scraping Config")
        
        # Multiple ranking URLs
        st.markdown("**Ranking Page URLs:**")
        ranking_urls = st.text_area(
            "Enter multiple URLs (one per line):",
            value="""https://engineering.careers360.com/colleges/ranking
https://engineering.careers360.com/colleges/ranking?state=maharashtra
https://engineering.careers360.com/colleges/ranking?category=government""",
            height=100
        )
        
        # Performance settings
        max_colleges_total = st.slider("Max colleges to scrape:", 5, 100, 20)
        max_workers = st.slider("Parallel workers:", 1, 10, 5)
        min_delay = st.slider("Min delay (seconds):", 0.5, 3.0, 1.0, 0.5)
        
        # Data selection
        st.markdown("**Data to Extract:**")
        include_courses = st.checkbox("Courses", value=True)
        include_admissions = st.checkbox("Admissions", value=True)
        include_placements = st.checkbox("Placements", value=True)
        
        # Scraping button
        if st.button("🚀 Start Efficient Scraping", type="primary"):
            st.session_state.start_scraping = True
        
        if st.button("🗑️ Clear Results"):
            st.session_state.scraped_colleges = []
            st.rerun()
    
    # Main scraping process
    if st.session_state.get('start_scraping'):
        st.session_state.efficient_scraper.min_delay = min_delay
        
        # Step 1: Extract college URLs from ranking pages
        st.info("📋 Extracting college URLs from ranking pages...")
        ranking_url_list = [url.strip() for url in ranking_urls.split('\n') if url.strip()]
        
        college_urls = st.session_state.efficient_scraper.scrape_college_urls_batch(
            ranking_url_list, max_colleges_per_url=max_colleges_total//len(ranking_url_list)
        )
        
        if not college_urls:
            st.error("❌ No college URLs found!")
            st.session_state.start_scraping = False
            st.stop()
        
        # Limit total colleges
        college_urls = college_urls[:max_colleges_total]
        st.success(f"✅ Found {len(college_urls)} college URLs")
        
        # Step 2: Parallel scraping of all colleges
        st.info(f"🔄 Scraping {len(college_urls)} colleges with {max_workers} parallel workers...")
        
        results = st.session_state.efficient_scraper.batch_scrape_colleges(
            college_urls, max_workers, include_courses, include_admissions, include_placements
        )
        
        st.session_state.scraped_colleges = results
        st.session_state.start_scraping = False
        
        # Show errors if any
        errors = []
        while not st.session_state.efficient_scraper.error_queue.empty():
            errors.append(st.session_state.efficient_scraper.error_queue.get())
        
        if errors:
            with st.expander(f"⚠️ {len(errors)} Errors Occurred"):
                for error in errors:
                    st.text(error)
        
        st.success(f"🎉 Completed! Scraped {len(results)} colleges successfully")
        st.rerun()
    
    # Display results
    if st.session_state.scraped_colleges:
        st.header(f"📊 Results ({len(st.session_state.scraped_colleges)} colleges)")
        
        # Export options
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export Detailed JSON"):
                json_data = json.dumps(st.session_state.scraped_colleges, indent=2)
                st.download_button(
                    "💾 Download JSON",
                    json_data,
                    "efficient_scrape_results.json",
                    "application/json"
                )
        
        with col2:
            if st.button("📊 Export Summary CSV"):
                summary_data = []
                for college in st.session_state.scraped_colleges:
                    summary_data.append({
                        'Name': college.get('name', 'Unknown'),
                        'URL': college.get('url', ''),
                        'Location': college.get('main', {}).get('location', 'N/A'),
                        'Established': college.get('main', {}).get('established', 'N/A'),
                        'Total_Courses': len(college.get('courses', [])),
                        'Placement_Rate': college.get('placements', {}).get('placement_rate', 'N/A'),
                        'Average_Package': college.get('placements', {}).get('average_package', 'N/A'),
                        'Scraped_Sections': ', '.join(college.get('scraped_sections', []))
                    })
                
                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    "💾 Download CSV",
                    csv,
                    "efficient_scrape_summary.csv",
                    "text/csv"
                )
        
        # Display colleges
        for i, college in enumerate(st.session_state.scraped_colleges):
            with st.expander(f"{i+1}. {college['name']} - {len(college.get('scraped_sections', []))} sections"):
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📋 Basic Info:**")
                    if 'main' in college:
                        main_data = college['main']
                        st.write(f"• **Location:** {main_data.get('location', 'N/A')}")
                        st.write(f"• **Established:** {main_data.get('established', 'N/A')}")
                        st.write(f"• **Type:** {main_data.get('type', 'N/A')}")
                    
                    st.markdown("**📚 Courses:**")
                    if 'courses' in college:
                        st.write(f"• **Total Courses:** {len(college['courses'])}")
                        if college['courses']:
                            for course in college['courses'][:3]:  # Show first 3
                                st.write(f"  - {course['name']}")
                            if len(college['courses']) > 3:
                                st.write(f"  - ... and {len(college['courses']) - 3} more")
                
                with col2:
                    st.markdown("**🎯 Admissions:**")
                    if 'admissions' in college:
                        adm_data = college['admissions']
                        if adm_data.get('entrance_exams'):
                            st.write(f"• **Exams:** {', '.join(adm_data['entrance_exams'])}")
                        st.write(f"• **App Fee:** {adm_data.get('application_fee', 'N/A')}")
                    
                    st.markdown("**💼 Placements:**")
                    if 'placements' in college:
                        pl_data = college['placements']
                        st.write(f"• **Rate:** {pl_data.get('placement_rate', 'N/A')}")
                        st.write(f"• **Avg Package:** {pl_data.get('average_package', 'N/A')}")
                        if pl_data.get('top_recruiters'):
                            st.write(f"• **Recruiters:** {', '.join(pl_data['top_recruiters'][:3])}")
                
                st.markdown(f"**🔗 URL:** {college['url']}")

if __name__ == "__main__":
    main()
