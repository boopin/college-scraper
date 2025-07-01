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
</style>
""", unsafe_allow_html=True)

class CollegeScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def make_request(self, url: str, delay: float = 1.0) -> Optional[BeautifulSoup]:
        """Make HTTP request with error handling"""
        try:
            time.sleep(delay)
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            st.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def extract_colleges_from_ranking(self, url: str) -> List[Dict]:
        """Extract college list from ranking page"""
        soup = self.make_request(url)
        if not soup:
            return []
        
        colleges = []
        
        # Try multiple selectors for college listings
        college_selectors = [
            'tr[data-college-id]',  # Table rows with college data
            '.college-list-item',   # College list items
            '.ranking-item',        # Ranking items
            'tbody tr',             # Table body rows
            '.college-card'         # College cards
        ]
        
        for selector in college_selectors:
            elements = soup.select(selector)
            if elements:
                st.info(f"Found {len(elements)} colleges using selector: {selector}")
                break
        else:
            # Fallback: look for any links containing 'university' or 'college'
            all_links = soup.find_all('a', href=True)
            college_links = [link for link in all_links 
                           if 'university' in link['href'] or 'college' in link['href']]
            elements = college_links[:20]  # Limit to first 20
            st.info(f"Fallback: Found {len(elements)} college links")
        
        for i, element in enumerate(elements[:50]):  # Limit to 50 colleges
            try:
                college_data = self.extract_college_basic_info(element, url)
                if college_data:
                    colleges.append(college_data)
            except Exception as e:
                st.warning(f"Error extracting college {i+1}: {str(e)}")
                continue
                
        return colleges
    
    def extract_college_basic_info(self, element, base_url: str) -> Optional[Dict]:
        """Extract basic college information from element"""
        try:
            # Find college name
            name_selectors = [
                'a[href*="university"]',
                '.college-name',
                '.university-name', 
                'td a',
                'h3 a',
                'h2 a'
            ]
            
            college_link = None
            college_name = "Unknown College"
            
            for selector in name_selectors:
                link_elem = element.select_one(selector)
                if link_elem:
                    college_link = urljoin(base_url, link_elem.get('href', ''))
                    college_name = link_elem.get_text(strip=True)
                    break
            
            if not college_link or 'university' not in college_link:
                return None
            
            # Extract additional info
            rank = self.extract_text_by_selectors(element, [
                '.rank', '.ranking', 'td:first-child', '.position'
            ]) or "N/A"
            
            rating = self.extract_text_by_selectors(element, [
                '.rating', '.stars', '.grade', '.score'
            ]) or "N/A"
            
            location = self.extract_text_by_selectors(element, [
                '.location', '.city', '.state', '.address'
            ]) or "N/A"
            
            fees = self.extract_text_by_selectors(element, [
                '.fees', '.tuition', '.cost', '.price'
            ]) or "N/A"
            
            return {
                'name': college_name,
                'rank': rank,
                'rating': rating,
                'location': location,
                'fees': fees,
                'college_url': college_link,
                'courses_url': college_link.replace('/university/', '/university/').rstrip('/') + '/courses',
                'admission_url': college_link.replace('/university/', '/university/').rstrip('/') + '/admission',
                'placement_url': college_link.replace('/university/', '/university/').rstrip('/') + '/placement'
            }
            
        except Exception as e:
            st.warning(f"Error extracting basic info: {str(e)}")
            return None
    
    def extract_text_by_selectors(self, element, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors to extract text"""
        for selector in selectors:
            found = element.select_one(selector)
            if found:
                return found.get_text(strip=True)
        return None
    
    def scrape_courses(self, url: str) -> List[Dict]:
        """Scrape courses from college courses page"""
        soup = self.make_request(url)
        if not soup:
            return []
        
        courses = []
        
        # Look for course tables or cards
        course_selectors = [
            'table tbody tr',
            '.course-card',
            '.course-item',
            '.program-item'
        ]
        
        for selector in course_selectors:
            elements = soup.select(selector)
            if elements:
                break
        
        for element in elements:
            try:
                course_name = self.extract_text_by_selectors(element, [
                    '.course-name', 'td:first-child', 'h3', 'h4', '.program-name'
                ])
                
                if not course_name or len(course_name) < 5:
                    continue
                
                duration = self.extract_text_by_selectors(element, [
                    '.duration', '.years', '.period'
                ]) or "N/A"
                
                fees = self.extract_text_by_selectors(element, [
                    '.fees', '.tuition', '.cost'
                ]) or "N/A"
                
                seats = self.extract_text_by_selectors(element, [
                    '.seats', '.intake', '.capacity'
                ]) or "N/A"
                
                courses.append({
                    'name': course_name,
                    'duration': duration,
                    'fees': fees,
                    'seats': seats
                })
                
            except Exception as e:
                continue
        
        return courses
    
    def scrape_admissions(self, url: str) -> Dict:
        """Scrape admission information"""
        soup = self.make_request(url)
        if not soup:
            return {}
        
        admission_data = {
            'eligibility': [],
            'entrance_exams': [],
            'important_dates': []
        }
        
        # Extract eligibility criteria
        eligibility_text = soup.get_text()
        if 'eligibility' in eligibility_text.lower():
            # Look for common eligibility patterns
            patterns = [
                r'10\+2.*?with.*?(\d+)%',
                r'Bachelor.*?degree',
                r'Graduation.*?with.*?(\d+)%'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, eligibility_text, re.IGNORECASE)
                admission_data['eligibility'].extend(matches)
        
        # Extract entrance exams
        exam_keywords = ['JEE', 'GATE', 'CAT', 'MAT', 'NEET', 'CLAT']
        for keyword in exam_keywords:
            if keyword in eligibility_text:
                admission_data['entrance_exams'].append(keyword)
        
        return admission_data
    
    def scrape_placements(self, url: str) -> Dict:
        """Scrape placement information"""
        soup = self.make_request(url)
        if not soup:
            return {}
        
        placement_data = {
            'placement_rate': 'N/A',
            'average_package': 'N/A',
            'highest_package': 'N/A',
            'top_recruiters': []
        }
        
        text = soup.get_text()
        
        # Extract placement statistics using regex
        placement_patterns = {
            'placement_rate': r'(\d+)%.*?placed',
            'average_package': r'average.*?package.*?₹?\s*(\d+\.?\d*\s*(?:lakh|crore))',
            'highest_package': r'highest.*?package.*?₹?\s*(\d+\.?\d*\s*(?:lakh|crore))'
        }
        
        for key, pattern in placement_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                placement_data[key] = match.group(1)
        
        # Extract top recruiters
        recruiter_keywords = ['Microsoft', 'Google', 'Amazon', 'TCS', 'Infosys', 'Wipro', 'IBM', 'Accenture']
        for keyword in recruiter_keywords:
            if keyword in text:
                placement_data['top_recruiters'].append(keyword)
        
        return placement_data

def main():
    st.markdown('<h1 class="main-header">🎓 Careers360 College Scraper</h1>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'scraper' not in st.session_state:
        st.session_state.scraper = CollegeScraper()
    if 'scraped_data' not in st.session_state:
        st.session_state.scraped_data = []
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Scraper Configuration")
        
        base_url = st.text_input(
            "Base URL:",
            value="https://engineering.careers360.com/colleges/ranking",
            help="Enter the Careers360 ranking page URL"
        )
        
        max_colleges = st.slider("Max Colleges:", 1, 50, 5)
        delay_seconds = st.slider("Delay (seconds):", 0.5, 5.0, 2.0, 0.5)
        
        scrape_mode = st.selectbox(
            "Scrape Mode:",
            ["Basic Info Only", "Include Courses", "Full Data (Courses + Admissions + Placements)"]
        )
        
        if st.button("🚀 Start Scraping", type="primary"):
            st.session_state.scraping = True
        
        st.markdown("---")
        st.markdown("### 📊 Current Session")
        st.metric("Colleges Scraped", len(st.session_state.scraped_data))
        
        if st.session_state.scraped_data:
            if st.button("🗑️ Clear Data"):
                st.session_state.scraped_data = []
                st.rerun()
    
    # Main content area
    if st.session_state.get('scraping', False):
        with st.spinner("🔍 Scraping colleges..."):
            # Step 1: Get college list
            st.info("📋 Fetching college rankings...")
            colleges = st.session_state.scraper.extract_colleges_from_ranking(base_url)
            
            if not colleges:
                st.error("❌ No colleges found. Please check the URL or try a different page.")
                st.session_state.scraping = False
                return
            
            colleges = colleges[:max_colleges]
            st.success(f"✅ Found {len(colleges)} colleges to scrape")
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 2: Scrape each college
            for i, college in enumerate(colleges):
                status_text.text(f"🏫 Scraping {college['name']} ({i+1}/{len(colleges)})...")
                progress_bar.progress((i + 1) / len(colleges))
                
                # Add courses if requested
                if scrape_mode in ["Include Courses", "Full Data (Courses + Admissions + Placements)"]:
                    college['courses'] = st.session_state.scraper.scrape_courses(college['courses_url'])
                
                # Add full data if requested
                if scrape_mode == "Full Data (Courses + Admissions + Placements)":
                    college['admissions'] = st.session_state.scraper.scrape_admissions(college['admission_url'])
                    college['placements'] = st.session_state.scraper.scrape_placements(college['placement_url'])
                
                st.session_state.scraped_data.append(college)
                time.sleep(delay_seconds)
            
            status_text.text("✅ Scraping completed!")
            st.session_state.scraping = False
            st.rerun()
    
    # Display results
    if st.session_state.scraped_data:
        st.header("📊 Scraped Data")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Colleges", len(st.session_state.scraped_data))
        with col2:
            total_courses = sum(len(college.get('courses', [])) for college in st.session_state.scraped_data)
            st.metric("Total Courses", total_courses)
        with col3:
            avg_rank = sum(int(re.findall(r'\d+', college.get('rank', '0'))[0]) if re.findall(r'\d+', college.get('rank', '0')) else 0 for college in st.session_state.scraped_data) / len(st.session_state.scraped_data)
            st.metric("Avg Rank", f"{avg_rank:.1f}")
        with col4:
            if st.button("📥 Export Data"):
                # Prepare data for download
                df = pd.DataFrame(st.session_state.scraped_data)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📄 Download CSV",
                    data=csv,
                    file_name=f"colleges_data_{len(st.session_state.scraped_data)}_colleges.csv",
                    mime="text/csv"
                )
                
                json_data = json.dumps(st.session_state.scraped_data, indent=2)
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name=f"colleges_data_{len(st.session_state.scraped_data)}_colleges.json",
                    mime="application/json"
                )
        
        # Display colleges
        for college in st.session_state.scraped_data:
            with st.expander(f"🏫 {college['name']} (Rank: {college['rank']})"):
                
                # Basic info
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Basic Information:**")
                    st.write(f"• **Rank:** {college['rank']}")
                    st.write(f"• **Rating:** {college['rating']}")
                    st.write(f"• **Location:** {college['location']}")
                    st.write(f"• **Fees:** {college['fees']}")
                
                with col2:
                    st.write("**URLs:**")
                    st.write(f"• [College Page]({college['college_url']})")
                    st.write(f"• [Courses]({college['courses_url']})")
                    st.write(f"• [Admissions]({college['admission_url']})")
                    st.write(f"• [Placements]({college['placement_url']})")
                
                # Courses
                if 'courses' in college and college['courses']:
                    st.write("**Courses:**")
                    courses_df = pd.DataFrame(college['courses'])
                    st.dataframe(courses_df, use_container_width=True)
                
                # Placements
                if 'placements' in college and college['placements']:
                    st.write("**Placement Data:**")
                    pl_data = college['placements']
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Placement Rate", pl_data.get('placement_rate', 'N/A'))
                    with col2:
                        st.metric("Average Package", pl_data.get('average_package', 'N/A'))
                    with col3:
                        st.metric("Highest Package", pl_data.get('highest_package', 'N/A'))
                    
                    if pl_data.get('top_recruiters'):
                        st.write("**Top Recruiters:**", ", ".join(pl_data['top_recruiters']))

if __name__ == "__main__":
    main()
