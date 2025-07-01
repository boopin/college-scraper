import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import re
from urllib.parse import urljoin, urlparse
import concurrent.futures
from typing import List, Dict, Optional

# Page config
st.set_page_config(
    page_title="Careers360 College Scraper",
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
    .college-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        background: #f8f9fa;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-container {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .status-success {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .status-error {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    .course-item {
        background: white;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 6px;
        border-left: 4px solid #667eea;
    }
    .placement-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    .stat-box {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

class ComprehensiveCollegeScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
    def make_request(self, url: str, delay: float = 1.0) -> Optional[BeautifulSoup]:
        """Make HTTP request with error handling"""
        try:
            time.sleep(delay)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            st.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def extract_colleges_from_ranking(self, url: str, max_colleges: int = 10) -> List[Dict]:
        """Extract college list from ranking page with comprehensive data"""
        soup = self.make_request(url)
        if not soup:
            return []
        
        colleges = []
        
        # Strategy 1: Look for structured college data in tables
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            if len(rows) > 3:  # Likely a college ranking table
                st.info(f"Found ranking table with {len(rows)} rows")
                for i, row in enumerate(rows[:max_colleges]):
                    college_data = self.extract_from_table_row(row, i + 1, url)
                    if college_data:
                        colleges.append(college_data)
                if colleges:
                    break
        
        # Strategy 2: Look for college cards or list items
        if not colleges:
            selectors = [
                '.college-item', '.university-item', '.ranking-item',
                '.college-card', '.university-card', '[data-college]',
                '.list-item', '.search-result'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    st.info(f"Found {len(elements)} college items using selector: {selector}")
                    for i, element in enumerate(elements[:max_colleges]):
                        college_data = self.extract_from_element(element, i + 1, url)
                        if college_data:
                            colleges.append(college_data)
                    break
        
        # Strategy 3: Extract from any links containing university/college
        if not colleges:
            all_links = soup.find_all('a', href=True)
            college_links = []
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if ('university' in href or 'college' in href) and len(text) > 5:
                    college_links.append((link, text, href))
            
            if college_links:
                st.info(f"Found {len(college_links)} college links")
                for i, (link, text, href) in enumerate(college_links[:max_colleges]):
                    college_data = self.extract_from_link(link, text, href, i + 1, url)
                    if college_data:
                        colleges.append(college_data)
        
        return colleges
    
    def extract_from_table_row(self, row, rank: int, base_url: str) -> Optional[Dict]:
        """Extract college data from table row"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            # Find college name and link
            college_link = None
            college_name = None
            
            for cell in cells:
                link = cell.find('a', href=True)
                if link and 'university' in link.get('href', ''):
                    college_link = urljoin(base_url, link['href'])
                    college_name = link.get_text(strip=True)
                    break
            
            if not college_name or not college_link:
                return None
            
            # Extract additional data from cells
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Try to extract fees, location, rating from cell content
            fees = self.extract_fees_from_text(' '.join(cell_texts))
            location = self.extract_location_from_text(' '.join(cell_texts))
            rating = self.extract_rating_from_text(' '.join(cell_texts))
            
            return {
                'name': college_name,
                'rank': rank,
                'rating': rating or 'N/A',
                'location': location or 'N/A',
                'fees': fees or 'N/A',
                'college_url': college_link,
                'courses_url': college_link.rstrip('/') + '/courses',
                'admission_url': college_link.rstrip('/') + '/admission',
                'placement_url': college_link.rstrip('/') + '/placement',
                'source': 'table_row'
            }
        except Exception as e:
            return None
    
    def extract_from_element(self, element, rank: int, base_url: str) -> Optional[Dict]:
        """Extract college data from generic element"""
        try:
            # Find college link
            link = element.find('a', href=True)
            if not link:
                return None
            
            college_link = urljoin(base_url, link['href'])
            college_name = link.get_text(strip=True)
            
            if not college_name or len(college_name) < 3:
                return None
            
            # Extract additional info from element text
            element_text = element.get_text()
            
            return {
                'name': college_name,
                'rank': rank,
                'rating': self.extract_rating_from_text(element_text) or 'N/A',
                'location': self.extract_location_from_text(element_text) or 'N/A',
                'fees': self.extract_fees_from_text(element_text) or 'N/A',
                'college_url': college_link,
                'courses_url': college_link.rstrip('/') + '/courses',
                'admission_url': college_link.rstrip('/') + '/admission',
                'placement_url': college_link.rstrip('/') + '/placement',
                'source': 'element'
            }
        except Exception as e:
            return None
    
    def extract_from_link(self, link, text: str, href: str, rank: int, base_url: str) -> Optional[Dict]:
        """Extract basic college data from link"""
        try:
            college_link = urljoin(base_url, href)
            
            return {
                'name': text,
                'rank': rank,
                'rating': 'N/A',
                'location': 'N/A',
                'fees': 'N/A',
                'college_url': college_link,
                'courses_url': college_link.rstrip('/') + '/courses',
                'admission_url': college_link.rstrip('/') + '/admission',
                'placement_url': college_link.rstrip('/') + '/placement',
                'source': 'link'
            }
        except Exception as e:
            return None
    
    def extract_fees_from_text(self, text: str) -> Optional[str]:
        """Extract fees from text using regex"""
        fee_patterns = [
            r'₹[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|L|Cr))?',
            r'Rs\.?\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|L|Cr))?',
            r'[\d,]+(?:\.\d+)?\s*(?:lakh|crore|L|Cr)'
        ]
        
        for pattern in fee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return None
    
    def extract_location_from_text(self, text: str) -> Optional[str]:
        """Extract location from text"""
        # Common Indian states and cities
        locations = [
            'Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata', 'Hyderabad',
            'Pune', 'Ahmedabad', 'Surat', 'Jaipur', 'Lucknow', 'Kanpur',
            'Maharashtra', 'Tamil Nadu', 'Karnataka', 'Gujarat', 'Rajasthan',
            'Uttar Pradesh', 'West Bengal', 'Andhra Pradesh', 'Telangana',
            'Kerala', 'Odisha', 'Punjab', 'Haryana', 'Madhya Pradesh'
        ]
        
        for location in locations:
            if location.lower() in text.lower():
                return location
        
        # Try to extract state patterns
        state_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*India\b'
        match = re.search(state_pattern, text)
        if match:
            return match.group(1)
        
        return None
    
    def extract_rating_from_text(self, text: str) -> Optional[str]:
        """Extract rating from text"""
        rating_patterns = [
            r'[A-Z]{1,5}(?:\+)?',  # AAAAA, AAA+, etc.
            r'\d\.\d+/\d+',         # 4.5/5
            r'\d\.\d+\s*stars?',    # 4.5 stars
            r'\d+/\d+',             # 9/10
        ]
        
        for pattern in rating_patterns:
            match = re.search(pattern, text)
            if match:
                rating = match.group(0)
                # Validate it's likely a rating
                if 'A' in rating or ('.' in rating and len(rating) < 10):
                    return rating
        return None
    
    def scrape_courses(self, url: str) -> List[Dict]:
        """Scrape courses from college courses page"""
        soup = self.make_request(url, delay=2.0)
        if not soup:
            return []
        
        courses = []
        
        # Strategy 1: Look for course tables
        tables = soup.find_all('table')
        for table in tables:
            course_rows = table.find_all('tr')[1:]  # Skip header
            if len(course_rows) > 2:  # Likely a courses table
                for row in course_rows:
                    course_data = self.extract_course_from_row(row)
                    if course_data:
                        courses.append(course_data)
                if courses:
                    break
        
        # Strategy 2: Look for course cards/items
        if not courses:
            course_selectors = [
                '.course-card', '.course-item', '.program-card', '.program-item',
                '.course-details', '.course-info', '[data-course]'
            ]
            
            for selector in course_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements[:20]:  # Limit courses
                        course_data = self.extract_course_from_element(element)
                        if course_data:
                            courses.append(course_data)
                    break
        
        # Strategy 3: Text pattern matching
        if not courses:
            page_text = soup.get_text()
            courses = self.extract_courses_from_text(page_text)
        
        return courses[:15]  # Limit to 15 courses
    
    def extract_course_from_row(self, row) -> Optional[Dict]:
        """Extract course data from table row"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # First cell usually contains course name
            course_name = cell_texts[0]
            if len(course_name) < 5 or not any(keyword in course_name.lower() 
                                             for keyword in ['tech', 'mba', 'mca', 'msc', 'ma', 'ba', 'bca', 'bsc']):
                return None
            
            # Try to extract other details
            all_text = ' '.join(cell_texts)
            
            return {
                'name': course_name,
                'duration': self.extract_duration_from_text(all_text) or 'N/A',
                'fees': self.extract_fees_from_text(all_text) or 'N/A',
                'seats': self.extract_seats_from_text(all_text) or 'N/A',
                'mode': 'Full Time'  # Default assumption
            }
        except Exception as e:
            return None
    
    def extract_course_from_element(self, element) -> Optional[Dict]:
        """Extract course data from element"""
        try:
            text = element.get_text()
            
            # Look for course name patterns
            course_patterns = [
                r'(B\.Tech[^,\n]*)', r'(M\.Tech[^,\n]*)', r'(MBA[^,\n]*)',
                r'(BCA[^,\n]*)', r'(MCA[^,\n]*)', r'(M\.Sc[^,\n]*)',
                r'(Bachelor[^,\n]*)', r'(Master[^,\n]*)'
            ]
            
            for pattern in course_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    course_name = match.group(1).strip()
                    return {
                        'name': course_name,
                        'duration': self.extract_duration_from_text(text) or 'N/A',
                        'fees': self.extract_fees_from_text(text) or 'N/A',
                        'seats': self.extract_seats_from_text(text) or 'N/A',
                        'mode': 'Full Time'
                    }
            return None
        except Exception as e:
            return None
    
    def extract_courses_from_text(self, text: str) -> List[Dict]:
        """Extract courses using text patterns"""
        courses = []
        
        course_patterns = [
            r'B\.Tech(?:\s+in)?\s+([^,\n\.]+)',
            r'M\.Tech(?:\s+in)?\s+([^,\n\.]+)',
            r'MBA(?:\s+in)?\s+([^,\n\.]*)',
            r'Bachelor\s+of\s+([^,\n\.]+)',
            r'Master\s+of\s+([^,\n\.]+)'
        ]
        
        for pattern in course_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:  # Limit matches per pattern
                if len(match.strip()) > 3:
                    courses.append({
                        'name': f"{pattern.split('(')[0].replace('\\s+', ' ').replace('\\', '')} {match.strip()}",
                        'duration': 'N/A',
                        'fees': 'N/A',
                        'seats': 'N/A',
                        'mode': 'N/A'
                    })
        
        return courses
    
    def extract_duration_from_text(self, text: str) -> Optional[str]:
        """Extract course duration"""
        duration_pattern = r'(\d+)\s*(?:year|yr)s?'
        match = re.search(duration_pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} Years"
        return None
    
    def extract_seats_from_text(self, text: str) -> Optional[str]:
        """Extract seat count"""
        seats_pattern = r'(\d+)\s*(?:seat|intake)'
        match = re.search(seats_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None
    
    def scrape_placements(self, url: str) -> Dict:
        """Scrape placement statistics"""
        soup = self.make_request(url, delay=2.0)
        if not soup:
            return {}
        
        text = soup.get_text()
        
        placement_data = {
            'placement_rate': self.extract_placement_rate(text),
            'average_package': self.extract_package(text, 'average'),
            'highest_package': self.extract_package(text, 'highest'),
            'median_package': self.extract_package(text, 'median'),
            'top_recruiters': self.extract_recruiters(text)
        }
        
        return placement_data
    
    def extract_placement_rate(self, text: str) -> str:
        """Extract placement percentage"""
        patterns = [
            r'(\d+(?:\.\d+)?)%\s*(?:placement|placed)',
            r'placement.*?(\d+(?:\.\d+)?)%'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{match.group(1)}%"
        return 'N/A'
    
    def extract_package(self, text: str, package_type: str) -> str:
        """Extract salary package information"""
        patterns = [
            rf'{package_type}.*?package.*?₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)',
            rf'{package_type}.*?salary.*?₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA)',
            rf'₹\s*([\d,]+(?:\.\d+)?)\s*(?:lakh|crore|LPA).*?{package_type}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"₹{match.group(1)} LPA"
        return 'N/A'
    
    def extract_recruiters(self, text: str) -> List[str]:
        """Extract top recruiting companies"""
        recruiters = []
        
        # Common top recruiters
        company_keywords = [
            'Microsoft', 'Google', 'Amazon', 'Apple', 'Facebook', 'Netflix',
            'TCS', 'Infosys', 'Wipro', 'IBM', 'Accenture', 'Deloitte',
            'Goldman Sachs', 'Morgan Stanley', 'JPMorgan', 'McKinsey',
            'Samsung', 'Intel', 'Qualcomm', 'Adobe', 'Oracle',
            'Flipkart', 'Paytm', 'Ola', 'Uber', 'Swiggy', 'Zomato'
        ]
        
        for company in company_keywords:
            if company.lower() in text.lower():
                recruiters.append(company)
        
        return recruiters[:10]  # Top 10

def main():
    st.markdown('<h1 class="main-header">🎓 Comprehensive College Data Scraper</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'scraper' not in st.session_state:
        st.session_state.scraper = ComprehensiveCollegeScraper()
    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = []
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Scraper Configuration")
        
        base_url = st.text_input(
            "Careers360 URL:",
            value="https://engineering.careers360.com/colleges/ranking",
            help="Enter any Careers360 ranking or listing page"
        )
        
        max_colleges = st.slider("Max Colleges:", 1, 25, 8)
        delay_seconds = st.slider("Delay (seconds):", 1.0, 5.0, 2.5, 0.5)
        
        scrape_mode = st.selectbox(
            "Data to Extract:",
            ["Basic Info Only", "Basic + Courses", "Complete Data (Basic + Courses + Placements)"]
        )
        
        if st.button("🚀 Start Comprehensive Scraping", type="primary"):
            st.session_state.scraping = True
        
        st.markdown("---")
        st.markdown("### 📊 Current Session")
        st.metric("Colleges Scraped", len(st.session_state.scraped_data))
        
        if st.session_state.scraped_data:
            if st.button("🗑️ Clear All Data"):
                st.session_state.scraped_data = []
                st.rerun()
    
    # Main scraping process
    if st.session_state.get('scraping', False):
        with st.spinner("🔍 Starting comprehensive scraping..."):
            # Step 1: Extract college list
            st.info("📋 Extracting colleges from ranking page...")
            colleges = st.session_state.scraper.extract_colleges_from_ranking(base_url, max_colleges)
            
            if not colleges:
                st.error("❌ No colleges found. Please check the URL or try a different page.")
                st.session_state.scraping = False
                return
            
            st.success(f"✅ Found {len(colleges)} colleges to scrape")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 2: Enhanced scraping for each college
            for i, college in enumerate(colleges):
                status_text.text(f"🏫 Processing {college['name']} ({i+1}/{len(colleges)})...")
                progress_bar.progress((i + 1) / len(colleges))
                
                # Scrape courses if requested
                if scrape_mode in ["Basic + Courses", "Complete Data (Basic + Courses + Placements)"]:
                    with st.spinner(f"📚 Extracting courses from {college['name']}..."):
                        college['courses'] = st.session_state.scraper.scrape_courses(college['courses_url'])
                        if college['courses']:
                            st.success(f"Found {len(college['courses'])} courses")
                
                # Scrape placements if requested
                if scrape_mode == "Complete Data (Basic + Courses + Placements)":
                    with st.spinner(f"💼 Extracting placement data from {college['name']}..."):
                        college['placements'] = st.session_state.scraper.scrape_placements(college['placement_url'])
                        if any(v != 'N/A' for v in college['placements'].values() if isinstance(v, str)):
                            st.success("Found placement data")
                
                st.session_state.scraped_data.append(college)
                time.sleep(delay_seconds)
            
            status_text.text("✅ Comprehensive scraping completed!")
            st.session_state.scraping = False
            st.rerun()
    
    # Display comprehensive results
    if st.session_state.scraped_data:
        st.header("📊 Comprehensive College Data")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Colleges", len(st.session_state.scraped_data))
        with col2:
            total_courses = sum(len(college.get('courses', [])) for college in st.session_state.scraped_data)
            st.metric("Total Courses Found", total_courses)
        with col3:
            with_placements = sum(1 for college in st.session_state.scraped_data 
                                if college.get('placements', {}).get('placement_rate', 'N/A') != 'N/A')
            st.metric("Colleges with Placement Data", with_placements)
        with col4:
            if st.button("📥 Export All Data"):
                # Export options
                df_basic = pd.DataFrame([{
                    'Name': c['name'], 'Rank': c['rank'], 'Rating': c['rating'],
                    'Location': c['location'], 'Fees': c['fees'], 'URL': c['college_url'],
                    'Total_Courses': len(c.get('courses', [])),
                    'Placement_Rate': c.get('placements', {}).get('placement_rate', 'N/A'),
                    'Average_Package': c.get('placements', {}).get('average_package', 'N/A')
                } for c in st.session_state.scraped_data])
                
                csv = df_basic.to_csv(index=False)
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"comprehensive_colleges_data_{len(st.session_state.scraped_data)}.csv",
                    mime="text/csv"
                )
                
                json_data = json.dumps(st.session_state.scraped_data, indent=2)
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"comprehensive_colleges_data_{len(st.session_state.scraped_data)}.json",
                    mime="application/json"
                )
        
        # Display detailed college information
        for college in st.session_state.scraped_data:
            with st.expander(f"🏫 {college['name']} (Rank: {college['rank']}) - {college.get('source', 'unknown')} source"):
                
                # Basic information
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📋 Basic Information")
                    st.write(f"**Rank:** {college['rank']}")
                    st.write(f"**Rating:** {college['rating']}")
                    st.write(f"**Location:** {college['location']}")
                    st.write(f"**Fees:** {college['fees']}")
                
                with col2:
                    st.markdown("### 🔗 Quick Links")
                    st.markdown(f"- [🏠 College Homepage]({college['college_url']})")
                    st.markdown(f"- [📚 Courses Page]({college['courses_url']})")
                    st.markdown(f"- [🎯 Admissions]({college['admission_url']})")
                    st.markdown(f"- [💼 Placements]({college['placement_url']})")
                
                # Courses section
                if 'courses' in college and college['courses']:
                    st.markdown("### 📚 Available Courses")
                    
                    # Course summary
                    st.info(f"Found {len(college['courses'])} courses")
                    
                    # Display courses in a nice format
                    for course in college['courses']:
                        with st.container():
                            st.markdown(f"""
                            <div class="course-item">
                                <strong>{course['name']}</strong><br>
                                <small>Duration: {course['duration']} | Fees: {course['fees']} | Seats: {course['seats']} | Mode: {course['mode']}</small>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Placement section
                if 'placements' in college and college['placements']:
                    st.markdown("### 💼 Placement Statistics")
                    
                    pl_data = college['placements']
                    
                    # Placement metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Placement Rate", pl_data.get('placement_rate', 'N/A'))
                    with col2:
                        st.metric("Average Package", pl_data.get('average_package', 'N/A'))
                    with col3:
                        st.metric("Highest Package", pl_data.get('highest_package', 'N/A'))
                    with col4:
                        st.metric("Median Package", pl_data.get('median_package', 'N/A'))
                    
                    # Top recruiters
                    if pl_data.get('top_recruiters'):
                        st.markdown("**🏢 Top Recruiters:**")
                        recruiters_text = ", ".join(pl_data['top_recruiters'])
                        st.markdown(f"<div style='background: #f0f2f6; padding: 1rem; border-radius: 8px; margin: 0.5rem 0;'>{recruiters_text}</div>", unsafe_allow_html=True)
                
                # Data quality indicator
                st.markdown("---")
                data_quality_score = 0
                quality_items = []
                
                if college['rating'] != 'N/A':
                    data_quality_score += 20
                    quality_items.append("✅ Rating")
                else:
                    quality_items.append("❌ Rating")
                
                if college['location'] != 'N/A':
                    data_quality_score += 20
                    quality_items.append("✅ Location")
                else:
                    quality_items.append("❌ Location")
                
                if college['fees'] != 'N/A':
                    data_quality_score += 20
                    quality_items.append("✅ Fees")
                else:
                    quality_items.append("❌ Fees")
                
                if college.get('courses'):
                    data_quality_score += 20
                    quality_items.append(f"✅ Courses ({len(college['courses'])})")
                else:
                    quality_items.append("❌ Courses")
                
                if college.get('placements') and any(v != 'N/A' for v in college['placements'].values() if isinstance(v, str)):
                    data_quality_score += 20
                    quality_items.append("✅ Placements")
                else:
                    quality_items.append("❌ Placements")
                
                st.markdown(f"**📊 Data Quality: {data_quality_score}%**")
                st.markdown(" | ".join(quality_items))

    # Instructions and tips
    with st.expander("📖 How to Use This Comprehensive Scraper"):
        st.markdown("""
        ### 🎯 **What This Scraper Extracts:**
        
        **📋 Basic Information:**
        - College name, rank, rating
        - Location and fees information
        - Official website links
        
        **📚 Course Details:**
        - Course names (B.Tech, M.Tech, MBA, etc.)
        - Duration, fees, seat availability
        - Study modes and specializations
        
        **💼 Placement Data:**
        - Placement rates and packages
        - Top recruiting companies
        - Average, highest, and median salaries
        
        ### 🚀 **How to Use:**
        
        1. **Enter URL:** Use any Careers360 ranking or college listing page
        2. **Set Parameters:** Choose max colleges and delay between requests  
        3. **Select Mode:** 
           - **Basic:** Just college info and links
           - **Basic + Courses:** Includes course details
           - **Complete:** Everything including placement data
        4. **Start Scraping:** Click the button and wait for results
        5. **Export Data:** Download as CSV or JSON when complete
        
        ### 🎯 **Best URLs to Try:**
        
        - **Main Ranking:** `https://engineering.careers360.com/colleges/ranking`
        - **State-wise:** `https://engineering.careers360.com/colleges/ranking?state=maharashtra`
        - **Category:** `https://engineering.careers360.com/colleges/ranking?category=government`
        - **Search Results:** Any search results page with college listings
        
        ### ⚡ **Performance Tips:**
        
        - **Start Small:** Use 5-8 colleges first to test
        - **Increase Delay:** Use 2-3 seconds delay to avoid rate limiting
        - **Check Results:** Verify data quality before large batches
        - **Export Frequently:** Download data as you go
        
        ### 🔧 **Troubleshooting:**
        
        - **No Colleges Found:** Try a different URL or page
        - **Missing Data:** Some pages may not have all information
        - **Slow Performance:** Increase delay or reduce max colleges
        - **Errors:** Check internet connection and try again
        
        ### 📊 **Data Quality:**
        
        Each college shows a data quality score based on:
        - ✅ **20%** for Rating information
        - ✅ **20%** for Location details  
        - ✅ **20%** for Fee information
        - ✅ **20%** for Course data
        - ✅ **20%** for Placement statistics
        
        ### 💡 **Pro Tips:**
        
        - **Multiple Sources:** Try different ranking pages for comprehensive data
        - **Verify Data:** Cross-check important information with official sources
        - **Regular Updates:** College data changes frequently, re-scrape periodically
        - **Backup Data:** Export and save your results regularly
        """)

if __name__ == "__main__":
    main()
