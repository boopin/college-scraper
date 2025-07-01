import streamlit as st
import requests
import re
import time
from urllib.parse import urljoin

# Page config
st.set_page_config(page_title="College Scraper", page_icon="🎓")

def fetch_page(url, delay=1):
    """Fetch webpage with basic error handling"""
    try:
        time.sleep(delay)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def extract_college_links(html_content, base_url):
    """Extract college links using regex (no BeautifulSoup dependency)"""
    if not html_content:
        return []
    
    # Find all links containing 'university' in href
    university_pattern = r'<a[^>]*href=["\']([^"\']*university[^"\']*)["\'][^>]*>([^<]+)</a>'
    matches = re.findall(university_pattern, html_content, re.IGNORECASE)
    
    colleges = []
    seen_urls = set()
    
    for href, name in matches:
        # Clean up the URL
        if href.startswith('/'):
            full_url = urljoin(base_url, href)
        elif href.startswith('http'):
            full_url = href
        else:
            continue
            
        # Clean up the name
        clean_name = re.sub(r'<[^>]+>', '', name).strip()
        
        # Avoid duplicates and filter out very short names
        if full_url not in seen_urls and len(clean_name) > 5:
            colleges.append({
                'name': clean_name,
                'url': full_url,
                'rank': len(colleges) + 1
            })
            seen_urls.add(full_url)
            
            # Limit results
            if len(colleges) >= 20:
                break
    
    return colleges

def main():
    st.title("🎓 College Link Extractor")
    st.write("Extract college links from Careers360 pages")
    
    # Initialize session state
    if 'results' not in st.session_state:
        st.session_state.results = []
    
    # Input section
    with st.form("scraper_form"):
        url = st.text_input(
            "Enter Careers360 URL:",
            value="https://engineering.careers360.com/colleges/ranking",
            help="Any Careers360 page with college listings"
        )
        
        max_results = st.slider("Max results:", 5, 20, 10)
        
        submitted = st.form_submit_button("🔍 Extract Links")
    
    if submitted:
        if not url or 'careers360.com' not in url:
            st.error("Please enter a valid Careers360 URL")
            return
            
        with st.spinner("Fetching page..."):
            # Fetch the page
            html_content = fetch_page(url)
            
            if html_content:
                st.success("✅ Page fetched successfully!")
                
                # Extract college links
                with st.spinner("Extracting college links..."):
                    colleges = extract_college_links(html_content, url)
                    
                    if colleges:
                        # Limit results
                        colleges = colleges[:max_results]
                        st.session_state.results = colleges
                        st.success(f"🎯 Found {len(colleges)} colleges!")
                    else:
                        st.warning("No college links found on this page")
            else:
                st.error("Failed to fetch the page")
    
    # Display results
    if st.session_state.results:
        st.header(f"📊 Found {len(st.session_state.results)} Colleges")
        
        # Export button
        if st.button("📥 Download as CSV"):
            csv_data = "Name,URL,Rank\n"
            for college in st.session_state.results:
                csv_data += f'"{college["name"]}","{college["url"]}",{college["rank"]}\n'
            
            st.download_button(
                label="💾 Download CSV",
                data=csv_data,
                file_name="colleges.csv",
                mime="text/csv"
            )
        
        # Display colleges
        for i, college in enumerate(st.session_state.results, 1):
            with st.expander(f"{i}. {college['name']}"):
                st.write(f"**Rank:** {college['rank']}")
                st.write(f"**URL:** [{college['url']}]({college['url']})")
                
                # Quick actions
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Visit {college['name'][:20]}...", key=f"visit_{i}"):
                        st.write("Click the URL link above to visit")
                with col2:
                    courses_url = college['url'].rstrip('/') + '/courses'
                    st.write(f"[View Courses]({courses_url})")
    
    # Clear results
    if st.session_state.results and st.button("🗑️ Clear Results"):
        st.session_state.results = []
        st.rerun()
    
    # Instructions
    with st.expander("📖 How to use"):
        st.write("""
        **This tool extracts college links from Careers360 pages:**
        
        1. **Enter a URL** from careers360.com (ranking pages work best)
        2. **Set max results** (how many colleges to find)
        3. **Click Extract Links** to start
        4. **Download CSV** to save the results
        
        **Good URLs to try:**
        - https://engineering.careers360.com/colleges/ranking
        - https://engineering.careers360.com/colleges/list-of-colleges
        - Any search results page
        
        **Note:** This extracts basic info only (name, URL, rank). 
        For detailed course/placement data, visit individual college pages.
        """)

if __name__ == "__main__":
    main()
