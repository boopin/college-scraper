import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional

# Page config
st.set_page_config(
    page_title="Individual College Scraper",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    .section-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
    }
    .data-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        background: #f8f9fa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .metric-item {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .course-table {
        background: white;
        border-radius: 8px;
        overflow: hidden;
        margin: 1rem 0;
    }
    .success-banner {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .error-banner {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    .info-banner {
        background: #d1ecf1;
        color: #0c5460;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class IndividualCollegeScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache'
        })
        
    def make_request(self, url: str, delay: float = 2.0) -> Optional[BeautifulSoup]:
        """Make HTTP request with comprehensive error handling"""
        try:
            st.info(f"🌐 Fetching: {url}")
            time.sleep(delay)
            
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            
            # Check if we got actual content
            if len(response.content) < 1000:
                st.warning(f"⚠️ Received very small response ({len(response.content)} bytes)")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug: Show page title
            title = soup.find('title')
            if title:
                st.success(f"✅ Successfully loaded: {title.get_text()[:100]}...")
            
            return soup
            
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Network error for {url}: {str(e)}")
            return None
        except Exception as e:
            st.error(f"❌ Parsing error for {url}: {str(e)}")
            return None
    
    def scrape_college_overview(self, url: str) -> Dict:
        """Scrape basic college information from main page"""
        soup = self.make_request(url)
        if not soup:
            return {}
        
        college_data = {
            'name': 'Unknown College',
            'location': 'N/A',
            'established': 'N/A',
            'type': 'N/A',
            'affiliation': 'N/A',
            'website': 'N/A',
            'ranking': {},
            'overview': 'N/A'
        }
        
        # Extract college name
        name_selectors = [
            'h1', '.college-name', '.university-name', '.main-heading',
            '.page-title', '[data-college-name]'
        ]
        
        for selector in name_selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if len(name) > 5 and 'careers360' not in name.lower():
                    college_data['name'] = name
                    st.success(f"📝 Found college name: {name}")
                    break
        
        # Extract key information from page text
        page_text = soup.get_text()
        
        # Extract establishment year
        year_match = re.search(r'(?:established|founded).*?(\d{4})', page_text, re.IGNORECASE)
        if year_match:
            college_data['established'] = year_match.group(1)
        
        # Extract location
        location_patterns = [
            r'(?:located in|address|campus).*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+)',
            r'([A-Z][a-z]+,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,?\s*India',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, page_text)
            if match:
                college_data['location'] = match.group(1)
                break
        
        # Extract college type
        if 'government' in page_text.lower() or 'public' in page_text.lower():
            college_data['type'] = 'Government'
        elif 'private' in page_text.lower():
            college_data['type'] = 'Private'
        elif 'deemed' in page_text.lower():
            college_data['type'] = 'Deemed University'
        
        # Extract rankings if present
        rankings = self.extract_rankings(soup, page_text)
        if rankings:
            college_data['ranking'] = rankings
        
        # Extract overview/description
        overview_selectors = [
            '.overview', '.description', '.about', '.college-info',
            '.summary', '[data-overview]'
        ]
        
        for selector in overview_selectors:
            element = soup.select_one(selector)
            if element:
                overview = element.get_text(strip=True)
                if len(overview) > 100:
                    college_data['overview'] = overview[:500] + "..."
                    break
        
        return college_data
    
    def extract_rankings(self, soup: BeautifulSoup, text: str) -> Dict:
        """Extract ranking information"""
        rankings = {}
        
        # Common ranking patterns
        ranking_patterns = [
            (r'NIRF.*?rank.*?(\d+)', 'NIRF'),
            (r'rank.*?(\d+).*?NIRF', 'NIRF'),
            (r'QS.*?rank.*?(\d+)', 'QS'),
            (r'rank.*?(\d+).*?QS', 'QS'),
            (r'India Today.*?rank.*?(\d+)', 'India Today'),
            (r'Outlook.*?rank.*?(\d+)', 'Outlook')
        ]
        
        for pattern, source in ranking_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rankings[source] = match.group(1)
        
        return rankings
    
    def scrape_courses_page(self, url: str) -> List[Dict]:
        """Scrape detailed course information"""
        soup = self.make_request(url)
        if not soup:
            return []
        
        courses = []
        
        # Strategy 1: Look for course tables
        tables = soup.find_all('table')
        st.info(f"🔍 Found {len(tables)} tables on courses page")
        
        for i, table in enumerate(tables):
            table_courses = self.extract_courses_from_table(table, f"Table {i+1}")
            if table_courses:
                courses.extend(table_courses)
                st.success(f"✅ Extracted {len(table_courses)} courses from table {i+1}")
        
        # Strategy 2: Look for structured course elements
        course_selectors = [
            '.course-item', '.course-card', '.program-item', '.program-card',
            '.course-details', '.course-info', '[data-course]', '.course-list li'
        ]
        
        for selector in course_selectors:
            elements = soup.select(selector)
            if elements:
                st.info(f"🔍 Found {len(elements)} course elements with selector: {selector}")
                for element in elements:
                    course_data = self.extract_course_from_element(element)
                    if course_data:
                        courses.append(course_data)
        
        # Strategy 3: Text-based extraction for specific course patterns
        if not courses:
            st.info("🔍 Attempting text-based course extraction...")
            text_courses = self.extract_courses_from_text(soup.get_text())
            courses.extend(text_courses)
        
        # Remove duplicates based on course name
        seen_names = set()
        unique_courses = []
        for course in courses:
            course_name = course.get('name', '').lower().strip()
            if course_name and course_name not in seen_names and len(course_name) > 3:
                seen_names.add(course_name)
                unique_courses.append(course)
        
        st.success(f"📚 Total unique courses found: {len(unique_courses)}")
        return unique_courses
    
    def extract_courses_from_table(self, table, table_name: str) -> List[Dict]:
        """Extract courses from HTML table"""
        courses = []
        
        try:
            # Get headers to understand table structure
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
            
            # Process data rows
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                
                # Try to identify course name (usually first column or contains degree keywords)
                course_name = None
                for i, cell_text in enumerate(cell_texts):
                    if any(keyword in cell_text.lower() for keyword in ['tech', 'mba', 'mca', 'msc', 'ma', 'ba', 'bca', 'bsc', 'diploma']):
                        if len(cell_text) > 5:
                            course_name = cell_text
                            break
                
                if not course_name and cell_texts[0] and len(cell_texts[0]) > 5:
                    course_name = cell_texts[0]
                
                if course_name:
                    # Extract additional details
                    course_data = {
                        'name': course_name,
                        'duration': self.extract_duration(' '.join(cell_texts)),
                        'fees': self.extract_fees(' '.join(cell_texts)),
                        'seats': self.extract_seats(' '.join(cell_texts)),
                        'eligibility': self.extract_eligibility(' '.join(cell_texts)),
                        'source': table_name
                    }
                    courses.append(course_data)
        
        except Exception as e:
            st.warning(f"⚠️ Error extracting from {table_name}: {str(e)}")
        
        return courses
    
    def extract_course_from_element(self, element) -> Optional[Dict]:
        """Extract course data from HTML element"""
        try:
            text = element.get_text()
            
            # Look for course name patterns
            course_patterns = [
                r'(B\.?Tech\.?\s+[^,\n]+)', r'(M\.?Tech\.?\s+[^,\n]+)',
                r'(MBA\s*[^,\n]*)', r'(BCA\s+[^,\n]+)', r'(MCA\s+[^,\n]+)',
                r'(M\.?Sc\.?\s+[^,\n]+)', r'(B\.?Sc\.?\s+[^,\n]+)',
                r'(Bachelor\s+of\s+[^,\n]+)', r'(Master\s+of\s+[^,\n]+)',
                r'(Diploma\s+in\s+[^,\n]+)', r'(Certificate\s+in\s+[^,\n]+)'
            ]
            
            for pattern in course_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    course_name = match.group(1).strip()
                    if len(course_name) > 5:
                        return {
                            'name': course_name,
                            'duration': self.extract_duration(text),
                            'fees': self.extract_fees(text),
                            'seats': self.extract_seats(text),
                            'eligibility': self.extract_eligibility(text),
                            'source': 'element'
                        }
            return None
        except Exception as e:
            return None
    
    def extract_courses_from_text(self, text: str) -> List[Dict]:
        """Extract courses using text pattern matching"""
        courses = []
        
        # More comprehensive course patterns
        patterns = [
            (r'B\.?Tech\.?\s+(?:in\s+)?([^,\n\.]{5,50})', 'B.Tech'),
            (r'M\.?Tech\.?\s+(?:in\s+)?([^,\n\.]{5,50})', 'M.Tech'),
            (r'MBA\s*(?:in\s+)?([^,\n\.]{0,30})', 'MBA'),
            (r'BCA\s+(?:in\s+)?([^,\n\.]{5,40})', 'BCA'),
            (r'MCA\s+(?:in\s+)?([^,\n\.]{5,40})', 'MCA'),
            (r'M\.?Sc\.?\s+(?:in\s+)?([^,\n\.]{5,40})', 'M.Sc'),
            (r'B\.?Sc\.?\s+(?:in\s+)?([^,\n\.]{5,40})', 'B.Sc'),
            (r'Diploma\s+in\s+([^,\n\.]{5,40})', 'Diploma'),
            (r'Bachelor\s+of\s+([^,\n\.]{5,40})', 'Bachelor'),
            (r'Master\s+of\s+([^,\n\.]{5,40})', 'Master')
        ]
        
        for pattern, prefix in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:10]:  # Limit matches per pattern
                if len(match.strip()) > 3:
                    full_name = f"{prefix} {match.strip()}" if match.strip() else prefix
                    courses.append({
                        'name': full_name,
                        'duration': 'N/A',
                        'fees': 'N/A',
                        'seats': 'N/A',
                        'eligibility': 'N/A',
                        'source': 'text_pattern'
                    })
        
        return courses
    
    def extract_duration(self, text: str) -> str:
        """Extract course duration"""
        patterns = [
            r'(\d+)\s*(?:year|yr)s?',
            r'(\d+)\s*(?:semester|sem)s?',
            r'duration[:\s]*(\d+\s*(?:year|yr)s?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) + " Years" if 'year' in pattern else match.group(0)
        return 'N/A'
    
    def extract_fees(self, text: str) -> str:
        """Extract fees information"""
        patterns = [
            r'₹\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|L|Cr))?',
            r'Rs\.?\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|L|Cr))?',
            r'fee[s]?[:\s]*₹\s*[\d,]+',
            r'fee[s]?[:\s]*Rs\.?\s*[\d,]+',
            r'[\d,]+(?:\.\d+)?\s*(?:lakh|crore|L|Cr)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return 'N/A'
    
    def extract_seats(self, text: str) -> str:
        """Extract seat information"""
        patterns = [
            r'(\d+)\s*seat[s]?',
            r'intake[:\s]*(\d+)',
            r'capacity[:\s]*(\d+)',
            r'admission[s]?[:\s]*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return 'N/A'
    
    def extract_eligibility(self, text: str) -> str:
        """Extract eligibility criteria"""
        patterns = [
            r'(?:eligibility|qualification)[:\s]*([^.!?]+[.!?])',
            r'10\+2[^.!?]*[.!?]',
            r'graduation[^.!?]*[.!?]',
            r'bachelor[^.!?]*[.!?]'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = match.group(0) if '10+2' in match.group(0) else match.group(1)
                return result.strip()[:200]  # Limit length
        return 'N/A'
    
    def scrape_admissions_page(self, url: str) -> Dict:
        """Scrape admission information"""
        soup = self.make_request(url)
        if not soup:
            return {}
        
        admission_data = {
            'eligibility_criteria': [],
            'entrance_exams': [],
            'application_process': [],
            'important_dates': [],
            'selection_process': 'N/A',
            'application_fee': 'N/A'
        }
        
        page_text = soup.get_text()
        
        # Extract entrance exams
        exam_keywords = [
            'JEE Main', 'JEE Advanced', 'GATE', 'CAT', 'MAT', 'XAT', 'GMAT',
            'NEET', 'CLAT', 'JAM', 'CSIR NET', 'UGC NET', 'TANCET', 'KCET'
        ]
        
        for exam in exam_keywords:
            if exam.lower() in page_text.lower():
                admission_data['entrance_exams'].append(exam)
        
        # Extract eligibility criteria patterns
        eligibility_patterns = [
            r'(?:eligibility|qualification)[^.!?]*(?:10\+2|graduation|bachelor)[^.!?]*[.!?]',
            r'(?:minimum|required)[^.!?]*(?:marks|percentage|CGPA)[^.!?]*[.!?]',
            r'(?:candidates|students)[^.!?]*(?:must|should|need)[^.!?]*[.!?]'
        ]
        
        for pattern in eligibility_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches[:5]:  # Limit to avoid too much text
                if len(match) > 20:
                    admission_data['eligibility_criteria'].append(match.strip())
        
        # Extract application fee
        fee_patterns = [
            r'application\s+fee[:\s]*₹\s*[\d,]+',
            r'registration\s+fee[:\s]*₹\s*[\d,]+',
            r'₹\s*[\d,]+[^.!?]*(?:application|registration)[^.!?]*fee'
        ]
        
        for pattern in fee_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                admission_data['application_fee'] = match.group(0)
                break
        
        # Extract important dates (simplified)
        date_patterns = [
            r'(?:last\s+date|deadline|application)[^.!?]*(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})',
            r'(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})[^.!?]*(?:last\s+date|deadline|application)'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches[:3]:  # Limit dates
                admission_data['important_dates'].append(match.strip())
        
        return admission_data
    
    def scrape_placements_page(self, url: str) -> Dict:
        """Scrape placement statistics"""
        soup = self.make_request(url)
        if not soup:
            return {}
        
        page_text = soup.get_text()
        
        placement_data = {
            'placement_rate': 'N/A',
            'average_package': 'N/A',
            'highest_package': 'N/A',
            'median_package': 'N/A',
            'lowest_package': 'N/A',
            'total_offers': 'N/A',
            'companies_visited': 'N/A',
            'top_recruiters': [],
            'sector_wise_placement': {}
        }
        
        # Extract placement statistics
        stats_patterns = {
            'placement_rate': [
                r'(\d+(?:\.\d+)?)%[^.!?]*(?:placement|placed)',
                r'placement[^.!?]*(\d+(?:\.\d+)?)%'
            ],
            'average_package': [
                r'average[^.!?]*package[^.!?]*₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)',
                r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)[^.!?]*average'
            ],
            'highest_package': [
                r'highest[^.!?]*package[^.!?]*₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)',
                r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)[^.!?]*highest'
            ],
            'median_package': [
                r'median[^.!?]*package[^.!?]*₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)',
                r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)[^.!?]*median'
            ]
        }
        
        for key, patterns in stats_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    if key == 'placement_rate':
                        placement_data[key] = f"{match.group(1)}%"
                    else:
                        placement_data[key] = f"₹{match.group(1)} LPA"
                    break
        
        # Extract top recruiters
        recruiter_keywords = [
            'Microsoft', 'Google', 'Amazon', 'Apple', 'Facebook', 'Netflix', 'Adobe',
            'TCS', 'Infosys', 'Wipro', 'IBM', 'Accenture', 'Deloitte', 'Capgemini',
            'Goldman Sachs', 'Morgan Stanley', 'JPMorgan', 'Deutsche Bank',
            'McKinsey', 'BCG', 'Bain', 'EY', 'PwC', 'KPMG',
            'Samsung', 'Intel', 'Qualcomm', 'Nvidia', 'Oracle', 'Salesforce',
            'Flipkart', 'Paytm', 'Ola', 'Uber', 'Swiggy', 'Zomato', 'PhonePe',
            'ISRO', 'DRDO', 'HAL', 'BHEL', 'ONGC', 'NTPC', 'L&T'
        ]
        
        for company in recruiter_keywords:
            if company.lower() in page_text.lower():
                placement_data['top_recruiters'].append(company)
        
        # Limit to top 15 recruiters
        placement_data['top_recruiters'] = placement_data['top_recruiters'][:15]
        
        return placement_data

def main():
    st.markdown('<h1 class="main-header">🎯 Individual College Page Scraper</h1>', unsafe_allow_html=True)
    st.markdown("**Specialized for scraping individual college pages like IIT Madras**")
    
    # Initialize session state
    if 'college_scraper' not in st.session_state:
        st.session_state.college_scraper = IndividualCollegeScraper()
    if 'college_data' not in st.session_state:
        st.session_state.college_data = {}
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ College Page Scraper")
        
        # College URL input
        college_url = st.text_input(
            "College Main Page URL:",
            value="https://www.careers360.com/university/indian-institute-of-technology-madras",
            help="Enter the main college page URL"
        )
        
        # Auto-generate related URLs
        if college_url:
            base_url = college_url.rstrip('/')
            courses_url = f"{base_url}/courses"
            admission_url = f"{base_url}/admission"
            placement_url = f"{base_url}/placement"
            
            st.markdown("**Auto-generated URLs:**")
            st.text_input("Courses URL:", value=courses_url, key="courses_url")
            st.text_input("Admission URL:", value=admission_url, key="admission_url")
            st.text_input("Placement URL:", value=placement_url, key="placement_url")
        
        # Scraping options
        delay_seconds = st.slider("Delay between requests:", 1.0, 5.0, 2.0, 0.5)
        
        # Individual scraping buttons
        st.markdown("### 🎯 Scrape Specific Sections")
        
        if st.button("🏫 Scrape College Overview", type="primary"):
            st.session_state.scraping = "overview"
        
        if st.button("📚 Scrape Courses"):
            st.session_state.scraping = "courses"
        
        if st.button("🎯 Scrape Admissions"):
            st.session_state.scraping = "admissions"
        
        if st.button("💼 Scrape Placements"):
            st.session_state.scraping = "placements"
        
        st.markdown("---")
        
        if st.button("🚀 Scrape All Sections", type="secondary"):
            st.session_state.scraping = "all"
        
        if st.button("🗑️ Clear Data"):
            st.session_state.college_data = {}
            st.rerun()
    
    # Main scraping logic
    if st.session_state.get('scraping'):
        scraping_mode = st.session_state.scraping
        
        if scraping_mode == "overview":
            with st.spinner("🔍 Scraping college overview..."):
                overview_data = st.session_state.college_scraper.scrape_college_overview(college_url)
                if overview_data:
                    st.session_state.college_data['overview'] = overview_data
                    st.success("✅ College overview scraped successfully!")
                else:
                    st.error("❌ Failed to scrape college overview")
        
        elif scraping_mode == "courses":
            with st.spinner("📚 Scraping courses data..."):
                courses_data = st.session_state.college_scraper.scrape_courses_page(st.session_state.courses_url)
                if courses_data:
                    st.session_state.college_data['courses'] = courses_data
                    st.success(f"✅ Found {len(courses_data)} courses!")
                else:
                    st.error("❌ No courses found")
        
        elif scraping_mode == "admissions":
            with st.spinner("🎯 Scraping admissions data..."):
                admissions_data = st.session_state.college_scraper.scrape_admissions_page(st.session_state.admission_url)
                if admissions_data:
                    st.session_state.college_data['admissions'] = admissions_data
                    st.success("✅ Admissions data scraped successfully!")
                else:
                    st.error("❌ Failed to scrape admissions data")
        
        elif scraping_mode == "placements":
            with st.spinner("💼 Scraping placements data..."):
                placements_data = st.session_state.college_scraper.scrape_placements_page(st.session_state.placement_url)
                if placements_data:
                    st.session_state.college_data['placements'] = placements_data
                    st.success("✅ Placements data scraped successfully!")
                else:
                    st.error("❌ Failed to scrape placements data")
        
        elif scraping_mode == "all":
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Overview
            status_text.text("🏫 Scraping college overview...")
            progress_bar.progress(0.2)
            overview_data = st.session_state.college_scraper.scrape_college_overview(college_url)
            if overview_data:
                st.session_state.college_data['overview'] = overview_data
            time.sleep(delay_seconds)
            
            # Step 2: Courses
            status_text.text("📚 Scraping courses...")
            progress_bar.progress(0.4)
            courses_data = st.session_state.college_scraper.scrape_courses_page(st.session_state.courses_url)
            if courses_data:
                st.session_state.college_data['courses'] = courses_data
            time.sleep(delay_seconds)
            
            # Step 3: Admissions
            status_text.text("🎯 Scraping admissions...")
            progress_bar.progress(0.7)
            admissions_data = st.session_state.college_scraper.scrape_admissions_page(st.session_state.admission_url)
            if admissions_data:
                st.session_state.college_data['admissions'] = admissions_data
            time.sleep(delay_seconds)
            
            # Step 4: Placements
            status_text.text("💼 Scraping placements...")
            progress_bar.progress(0.9)
            placements_data = st.session_state.college_scraper.scrape_placements_page(st.session_state.placement_url)
            if placements_data:
                st.session_state.college_data['placements'] = placements_data
            
            progress_bar.progress(1.0)
            status_text.text("✅ All sections scraped successfully!")
            st.success("🎉 Complete college data extracted!")
        
        st.session_state.scraping = None
        st.rerun()
    
    # Display results
    if st.session_state.college_data:
        
        # Export options
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Export JSON"):
                json_data = json.dumps(st.session_state.college_data, indent=2)
                st.download_button(
                    label="💾 Download JSON",
                    data=json_data,
                    file_name="college_data.json",
                    mime="application/json"
                )
        with col2:
            if st.button("📊 Export CSV Summary"):
                # Create summary CSV
                summary_data = []
                overview = st.session_state.college_data.get('overview', {})
                courses = st.session_state.college_data.get('courses', [])
                placements = st.session_state.college_data.get('placements', {})
                
                summary_data.append({
                    'College_Name': overview.get('name', 'N/A'),
                    'Location': overview.get('location', 'N/A'),
                    'Established': overview.get('established', 'N/A'),
                    'Type': overview.get('type', 'N/A'),
                    'Total_Courses': len(courses),
                    'Placement_Rate': placements.get('placement_rate', 'N/A'),
                    'Average_Package': placements.get('average_package', 'N/A'),
                    'Highest_Package': placements.get('highest_package', 'N/A')
                })
                
                df = pd.DataFrame(summary_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="💾 Download CSV",
                    data=csv,
                    file_name="college_summary.csv",
                    mime="text/csv"
                )
        
        # Display College Overview
        if 'overview' in st.session_state.college_data:
            st.markdown('<div class="section-header">🏫 College Overview</div>', unsafe_allow_html=True)
            
            overview = st.session_state.college_data['overview']
            
            with st.container():
                st.markdown('<div class="data-card">', unsafe_allow_html=True)
                
                # Basic info metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("College Name", overview.get('name', 'N/A'))
                with col2:
                    st.metric("Location", overview.get('location', 'N/A'))
                with col3:
                    st.metric("Established", overview.get('established', 'N/A'))
                with col4:
                    st.metric("Type", overview.get('type', 'N/A'))
                
                # Rankings if available
                if overview.get('ranking'):
                    st.markdown("**🏆 Rankings:**")
                    ranking_cols = st.columns(len(overview['ranking']))
                    for i, (source, rank) in enumerate(overview['ranking'].items()):
                        with ranking_cols[i]:
                            st.metric(f"{source} Rank", rank)
                
                # Overview text
                if overview.get('overview') and overview['overview'] != 'N/A':
                    st.markdown("**📝 Overview:**")
                    st.write(overview['overview'])
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Display Courses
        if 'courses' in st.session_state.college_data:
            st.markdown('<div class="section-header">📚 Courses Offered</div>', unsafe_allow_html=True)
            
            courses = st.session_state.college_data['courses']
            
            if courses:
                st.markdown(f'<div class="info-banner">Found {len(courses)} courses</div>', unsafe_allow_html=True)
                
                # Create courses DataFrame for better display
                courses_df = pd.DataFrame(courses)
                
                # Display as interactive table
                st.dataframe(
                    courses_df, 
                    use_container_width=True,
                    hide_index=True
                )
                
                # Course statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    btech_count = len([c for c in courses if 'tech' in c.get('name', '').lower() and 'b.' in c.get('name', '').lower()])
                    st.metric("B.Tech Courses", btech_count)
                with col2:
                    mtech_count = len([c for c in courses if 'tech' in c.get('name', '').lower() and 'm.' in c.get('name', '').lower()])
                    st.metric("M.Tech Courses", mtech_count)
                with col3:
                    other_count = len(courses) - btech_count - mtech_count
                    st.metric("Other Courses", other_count)
            else:
                st.warning("No courses data available")
        
        # Display Admissions
        if 'admissions' in st.session_state.college_data:
            st.markdown('<div class="section-header">🎯 Admission Information</div>', unsafe_allow_html=True)
            
            admissions = st.session_state.college_data['admissions']
            
            with st.container():
                st.markdown('<div class="data-card">', unsafe_allow_html=True)
                
                # Entrance Exams
                if admissions.get('entrance_exams'):
                    st.markdown("**📝 Entrance Exams:**")
                    exams_text = ", ".join(admissions['entrance_exams'])
                    st.markdown(f'<div class="metric-item">{exams_text}</div>', unsafe_allow_html=True)
                
                # Application Fee
                if admissions.get('application_fee') and admissions['application_fee'] != 'N/A':
                    st.markdown("**💰 Application Fee:**")
                    st.markdown(f'<div class="metric-item">{admissions["application_fee"]}</div>', unsafe_allow_html=True)
                
                # Eligibility Criteria
                if admissions.get('eligibility_criteria'):
                    st.markdown("**✅ Eligibility Criteria:**")
                    for i, criteria in enumerate(admissions['eligibility_criteria'][:3]):  # Show top 3
                        st.markdown(f'<div class="metric-item">{i+1}. {criteria}</div>', unsafe_allow_html=True)
                
                # Important Dates
                if admissions.get('important_dates'):
                    st.markdown("**📅 Important Dates:**")
                    for date in admissions['important_dates'][:3]:  # Show top 3
                        st.markdown(f'<div class="metric-item">• {date}</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        
        # Display Placements
        if 'placements' in st.session_state.college_data:
            st.markdown('<div class="section-header">💼 Placement Statistics</div>', unsafe_allow_html=True)
            
            placements = st.session_state.college_data['placements']
            
            with st.container():
                st.markdown('<div class="data-card">', unsafe_allow_html=True)
                
                # Placement metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Placement Rate", placements.get('placement_rate', 'N/A'))
                with col2:
                    st.metric("Average Package", placements.get('average_package', 'N/A'))
                with col3:
                    st.metric("Highest Package", placements.get('highest_package', 'N/A'))
                with col4:
                    st.metric("Median Package", placements.get('median_package', 'N/A'))
                
                # Top Recruiters
                if placements.get('top_recruiters'):
                    st.markdown("**🏢 Top Recruiters:**")
                    recruiters_text = ", ".join(placements['top_recruiters'])
                    st.markdown(f'<div class="metric-item">{recruiters_text}</div>', unsafe_allow_html=True)
                
                # Additional metrics if available
                additional_metrics = ['total_offers', 'companies_visited', 'lowest_package']
                additional_data = {k: v for k, v in placements.items() if k in additional_metrics and v != 'N/A'}
                
                if additional_data:
                    st.markdown("**📊 Additional Statistics:**")
                    for key, value in additional_data.items():
                        display_key = key.replace('_', ' ').title()
                        st.markdown(f'<div class="metric-item"><strong>{display_key}:</strong> {value}</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
    
    # Instructions
    with st.expander("📖 How to Use Individual College Scraper"):
        st.markdown("""
        ### 🎯 **Purpose:**
        This scraper is specifically designed for individual college pages on Careers360, like:
        - `https://www.careers360.com/university/[college-name]`
        - `https://www.careers360.com/university/[college-name]/courses`
        - `https://www.careers360.com/university/[college-name]/admission`
        - `https://www.careers360.com/university/[college-name]/placement`
        
        ### 🚀 **How to Use:**
        
        1. **Enter College URL:** Paste the main college page URL
        2. **Auto-Generated URLs:** The system automatically creates related URLs
        3. **Choose Scraping Mode:**
           - **Individual Sections:** Scrape one section at a time
           - **All Sections:** Comprehensive scraping of all pages
        4. **View Results:** Data appears in organized sections below
        5. **Export Data:** Download as JSON or CSV
        
        ### 📊 **What Gets Extracted:**
        
        **🏫 College Overview:**
        - College name, location, establishment year
        - College type (Government/Private/Deemed)
        - Rankings (NIRF, QS, etc.)
        - Overview/description
        
        **📚 Courses Page:**
        - Course names (B.Tech, M.Tech, MBA, etc.)
        - Duration, fees, seat availability
        - Eligibility criteria
        - Multiple extraction strategies for different page layouts
        
        **🎯 Admissions Page:**
        - Entrance exams required
        - Eligibility criteria
        - Application fees
        - Important dates
        - Selection process
        
        **💼 Placements Page:**
        - Placement rates and statistics
        - Average, highest, median packages
        - Top recruiting companies
        - Additional metrics (offers, companies visited)
        
        ### 🎯 **Best Practices:**
        
        - **Test Individual Sections:** Start with one section to verify data quality
        - **Use Delays:** 2-3 seconds between requests to avoid rate limiting
        - **Check Data Quality:** Review extracted information for accuracy
        - **Export Regularly:** Save your data as you collect it
        
        ### 🔧 **Troubleshooting:**
        
        - **No Data Found:** The page structure might be different; try individual sections
        - **Partial Data:** Some pages may not have all information sections
        - **Errors:** Check internet connection and try again with higher delays
        
        ### ✅ **Supported Colleges:**
        This scraper works best with major colleges on Careers360 that have structured pages:
        - IITs, NITs, IIITs
        - Major private engineering colleges
        - Business schools with dedicated pages
        - Any college with standard Careers360 page structure
        """)

if __name__ == "__main__":
    main()
