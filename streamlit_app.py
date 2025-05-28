import streamlit as st
import sqlite3
import pandas as pd
import time
import subprocess
import threading
import os
from typing import List
import plotly.express as px
import plotly.graph_objects as go

# Import the scraper functions
try:
    from indeed_scraper import scrape_indeed_jobs, init_database, get_database_stats, DB_NAME, TABLE_NAME
except ImportError:
    st.error("Could not import indeed_scraper    pip install streamlit plotly.py. Make sure it's in the same directory.")

st.set_page_config(page_title="Job Scraper Dashboard", page_icon="🔍", layout="wide")

st.title("🔍 Indeed Job Scraper Dashboard")
st.markdown("Configure and run job searches with real-time monitoring")

# Sidebar for configuration
st.sidebar.header("⚙️ Scraper Configuration")

# Job titles input
st.sidebar.subheader("Job Titles")
job_titles_text = st.sidebar.text_area(
    "Enter job titles (one per line)",
    value="key account manager\nproject manager\nbusiness analyst\nmarketing manager\ndata analyst",
    height=120
)
job_titles = [title.strip() for title in job_titles_text.split('\n') if title.strip()]

# Location and parameters
location = st.sidebar.text_input("Location", value="copenhagen, denmark")
results_per_title = st.sidebar.slider("Results per job title", min_value=10, max_value=200, value=50, step=10)
hours_old = st.sidebar.selectbox("Job age (hours)", options=[24, 72, 168, 336], index=2, format_func=lambda x: f"{x} hours ({x//24} days)")

# Advanced settings
with st.sidebar.expander("Advanced Settings"):
    country = st.text_input("Country", value="denmark")
    delay_between_searches = st.slider("Delay between searches (seconds)", min_value=1, max_value=10, value=3)

# Database functions
@st.cache_data
def load_job_data():
    """Load job data from database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

def get_job_stats():
    """Get job statistics from database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Total jobs
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_jobs = cursor.fetchone()[0]
        
        # Jobs by search term
        cursor.execute(f"SELECT search_term, COUNT(*) FROM {TABLE_NAME} GROUP BY search_term ORDER BY COUNT(*) DESC")
        jobs_by_term = cursor.fetchall()
        
        # Recent jobs (last 24 hours)
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE datetime(scraped_timestamp) > datetime('now', '-1 day')")
        recent_jobs = cursor.fetchone()[0]
        
        # Jobs with descriptions
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE description IS NOT NULL AND description != ''")
        jobs_with_desc = cursor.fetchone()[0]
        
        conn.close()
        return {
            'total': total_jobs,
            'recent': recent_jobs,
            'with_descriptions': jobs_with_desc,
            'by_term': jobs_by_term
        }
    except Exception:
        return {'total': 0, 'recent': 0, 'with_descriptions': 0, 'by_term': []}

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 Current Database Status")
    
    # Get current stats
    stats = get_job_stats()
    
    # Display metrics
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Total Jobs", stats['total'])
    with metric_cols[1]:
        st.metric("Last 24h", stats['recent'])
    with metric_cols[2]:
        st.metric("With Descriptions", stats['with_descriptions'])
    with metric_cols[3]:
        completion_rate = (stats['with_descriptions'] / stats['total'] * 100) if stats['total'] > 0 else 0
        st.metric("Completion Rate", f"{completion_rate:.1f}%")

with col2:
    st.header("🚀 Run Scraper")
    
    # Scraper controls
    if st.button("Start Scraping", type="primary", use_container_width=True):
        if not job_titles:
            st.error("Please enter at least one job title")
        else:
            # Initialize progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.empty()
            
            # Initialize database
            init_database()
            
            total_inserted = 0
            
            for i, job_title in enumerate(job_titles):
                status_text.text(f"Searching for: {job_title}")
                progress_bar.progress((i) / len(job_titles))
                
                try:
                    # Run scraper for this job title
                    inserted = scrape_indeed_jobs(job_title, location)
                    total_inserted += inserted
                    
                    # Update results
                    with results_container.container():
                        st.success(f"✅ {job_title}: {inserted} jobs added")
                    
                    # Delay between searches
                    if i < len(job_titles) - 1:
                        time.sleep(delay_between_searches)
                        
                except Exception as e:
                    with results_container.container():
                        st.error(f"❌ {job_title}: Error - {str(e)}")
            
            # Final update
            progress_bar.progress(1.0)
            status_text.text("Scraping completed!")
            st.success(f"🎉 Total jobs added: {total_inserted}")
            
            # Refresh the page data
            st.rerun()

# Display jobs by search term chart
if stats['by_term']:
    st.header("📈 Jobs by Search Term")
    
    terms_df = pd.DataFrame(stats['by_term'], columns=['Search Term', 'Count'])
    
    fig = px.bar(
        terms_df, 
        x='Search Term', 
        y='Count',
        title="Number of Jobs by Search Term",
        color='Count',
        color_continuous_scale='viridis'
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# Job data table
st.header("📋 Recent Job Postings")

# Load and display job data
job_data = load_job_data()
if not job_data.empty:
    # Filter options
    filter_cols = st.columns(3)
    with filter_cols[0]:
        search_term_filter = st.selectbox(
            "Filter by search term",
            options=['All'] + list(job_data['search_term'].unique())
        )
    with filter_cols[1]:
        company_filter = st.text_input("Filter by company (contains)")
    with filter_cols[2]:
        show_recent = st.checkbox("Show only recent (last 24h)", value=True)
    
    # Apply filters
    filtered_data = job_data.copy()
    
    if search_term_filter != 'All':
        filtered_data = filtered_data[filtered_data['search_term'] == search_term_filter]
    
    if company_filter:
        filtered_data = filtered_data[filtered_data['company'].str.contains(company_filter, case=False, na=False)]
    
    if show_recent:
        filtered_data['scraped_timestamp'] = pd.to_datetime(filtered_data['scraped_timestamp'])
        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=24)
        filtered_data = filtered_data[filtered_data['scraped_timestamp'] > cutoff_time]
    
    # Display results count
    st.write(f"Showing {len(filtered_data)} jobs")
    
    # Display table
    if not filtered_data.empty:
        # Select columns to display
        display_columns = [
            'title', 'company', 'location', 'job_type', 
            'search_term', 'scraped_timestamp'
        ]
        
        display_data = filtered_data[display_columns].copy()
        display_data['scraped_timestamp'] = pd.to_datetime(display_data['scraped_timestamp']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                'title': 'Job Title',
                'company': 'Company',
                'location': 'Location',
                'job_type': 'Type',
                'search_term': 'Search Term',
                'scraped_timestamp': 'Scraped At'
            }
        )
        
        # Export option
        if st.button("📥 Export to CSV"):
            csv = filtered_data.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"jobs_export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )
    else:
        st.info("No jobs found with current filters")
else:
    st.info("No job data available. Run the scraper to populate the database.")

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: Use the sidebar to configure your search parameters before running the scraper.")
