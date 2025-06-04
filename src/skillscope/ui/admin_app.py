import streamlit as st
import sqlite3
import pandas as pd
import time
import subprocess
import threading
import os
import sys
from typing import List
import plotly.express as px
import plotly.graph_objects as go

# Add the project root to Python path for proper imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

st.set_page_config(page_title="Job Scraper Dashboard", page_icon="🔍", layout="wide")

st.title("🔍 Indeed Job Scraper Dashboard")
st.markdown("Configure and run job searches with real-time monitoring")

# Import the scraper functions
try:
    from skillscope.scrapers.indeed_scraper import scrape_indeed_jobs, init_database, get_database_stats, DB_NAME, TABLE_NAME
    SCRAPER_AVAILABLE = True
except ImportError as e:
    st.error(f"Could not import scraper modules: {e}")
    SCRAPER_AVAILABLE = False
    # Set default values for missing variables
    DB_NAME = 'data/databases/indeed_jobs.db'
    TABLE_NAME = 'job_postings'

# Try to import data enrichment modules
try:
    from skillscope.core.data_enrichment import (
        run_data_enrichment_for_app, 
        get_enrichment_status, 
        quick_maintenance_check,
        run_quick_maintenance
    )
    ENRICHMENT_AVAILABLE = True
except ImportError as e:
    st.warning(f"Data enrichment modules not available: {e}")
    ENRICHMENT_AVAILABLE = False

# Function to standardize timestamp formats in the database
def standardize_timestamps():
    """Fix any inconsistent timestamp formats in the database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check for potential timestamp issues (ISO format with T and microseconds)
        timestamp_columns = ['scraped_timestamp']  # Only use columns that actually exist
        
        for column in timestamp_columns:
            # Find records with problematic timestamp format
            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE {column} LIKE '%T%' OR {column} LIKE '%.%'
            """)
            count = cursor.fetchone()[0]
            
            if count > 0:
                # Fix timestamps by converting to standard format
                cursor.execute(f"""
                    UPDATE {TABLE_NAME} SET {column} = 
                    SUBSTR({column}, 1, 10) || ' ' || SUBSTR({column}, 12, 8)
                    WHERE {column} LIKE '%T%'
                """)
                
                # Set null timestamps to current time
                cursor.execute(f"""
                    UPDATE {TABLE_NAME} SET {column} = DATETIME('now')
                    WHERE {column} IS NULL
                """)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error standardizing timestamps: {e}")
        return False

# Run timestamp standardization when the app starts
standardize_timestamps()

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
    if not SCRAPER_AVAILABLE:
        return {'total': 0, 'recent': 0, 'with_descriptions': 0, 'by_term': []}
    
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
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return {'total': 0, 'recent': 0, 'with_descriptions': 0, 'by_term': []}

# Main content area - Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["📊 Database Status", "🚀 Job Scraping", "🔍 Data Enrichment"])

with tab1:
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
        st.header("🔧 Quick Actions")
        
        # Database maintenance
        if st.button("🔧 Quick Maintenance", help="Clean up old and duplicate records"):
            with st.spinner("Running maintenance..."):
                # First standardize timestamps
                timestamp_fixed = standardize_timestamps()
                
                if ENRICHMENT_AVAILABLE:
                    maintenance_result = run_quick_maintenance()
                    if maintenance_result["success"]:
                        if timestamp_fixed:
                            st.success("✅ Timestamp formats standardized successfully")
                        
                        if maintenance_result["maintenance_performed"]:
                            st.success(f"✅ Maintenance completed! Cleaned {maintenance_result.get('records_cleaned', 0)} records")
                        else:
                            st.info("ℹ️ No maintenance needed - database is healthy")
                    else:
                        st.error(f"❌ Maintenance failed: {maintenance_result.get('error', 'Unknown error')}")
                else:
                    if timestamp_fixed:
                        st.success("✅ Timestamp formats standardized successfully")
                    else:
                        st.warning("ℹ️ Data enrichment module not available - only timestamp standardization performed")
        
        # Refresh data cache
        if st.button("🔄 Refresh Data", help="Reload data from database", key="refresh_data_actions"):
            st.cache_data.clear()
            st.success("✅ Data cache refreshed!")
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
        st.plotly_chart(fig, use_container_width=True, key="jobs_by_search_term_chart")

    # Job data table
    st.header("📋 Recent Job Postings")

    # Load and display job data
    job_data = load_job_data()
    if not job_data.empty:
        # Filter options
        filter_cols = st.columns(2)
        with filter_cols[0]:
            search_term_filter = st.selectbox(
                "Filter by search term",
                options=['All'] + list(job_data['search_term'].unique())
            )
        with filter_cols[1]:
            company_filter = st.text_input("Filter by company (contains)")
        
        # Apply filters
        filtered_data = job_data.copy()
        
        if search_term_filter != 'All':
            filtered_data = filtered_data[filtered_data['search_term'] == search_term_filter]
        
        if company_filter:
            filtered_data = filtered_data[filtered_data['company'].str.contains(company_filter, case=False, na=False)]
        
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
            
            # Handle potential timestamp formats safely
            try:
                # First ensure we have valid data in timestamp column
                display_data['scraped_timestamp'] = display_data['scraped_timestamp'].fillna(pd.Timestamp.now())
                
                # Convert using format='mixed' to handle both ISO8601 and regular formats
                display_data['scraped_timestamp'] = pd.to_datetime(
                    display_data['scraped_timestamp'], 
                    format='mixed', 
                    errors='coerce'
                ).dt.strftime('%Y-%m-%d %H:%M')
            except Exception as e:
                st.warning(f"Timestamp formatting issue: {e}. Try running the Quick Maintenance to fix.")
            
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
        
        # Refresh data cache
        if st.button("🔄 Refresh Data", help="Reload data from database", key="refresh_data_empty"):
            st.cache_data.clear()
            st.success("✅ Data cache refreshed!")
            st.rerun()

with tab2:
    st.header("🚀 Run Scraper")
    
    if not SCRAPER_AVAILABLE:
        st.error("❌ Job scraper module not available. Please check your installation and ensure python-jobspy is installed.")
        st.info("To install missing dependencies, run: `pip install python-jobspy`")
    else:
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

with tab3:
    st.header("🔍 Data Enrichment")
    
    if not ENRICHMENT_AVAILABLE:
        st.error("❌ Data enrichment module not available. Check your installation.")
    else:
        # Get enrichment status
        enrichment_status = get_enrichment_status()
        
        if not enrichment_status.get("database_exists", False):
            st.warning("⚠️ No database found. Please run the scraper first to populate the database.")
        else:
            # Display enrichment metrics
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Enrichment Status")
                
                metric_cols = st.columns(4)
                with metric_cols[0]:
                    st.metric("Total Records", enrichment_status['total_records'])
                with metric_cols[1]:
                    st.metric("Missing Company", enrichment_status['missing_data']['company'])
                with metric_cols[2]:
                    st.metric("Missing Industry", enrichment_status['missing_data']['industry'])
                with metric_cols[3]:
                    st.metric("Missing Description", enrichment_status['missing_data']['description'])
                
                # Progress bar for enrichment
                enrichment_pct = enrichment_status['enrichment_percentage']
                st.metric("Enrichment Progress", f"{enrichment_pct:.1f}%")
                st.progress(enrichment_pct / 100)
                
                # Data freshness
                freshness = enrichment_status.get('freshness_ratio', 0)
                st.metric("Data Freshness", f"{freshness:.2f}")
                
                # API status
                api_status = "✅ Configured" if enrichment_status['api_key_configured'] else "❌ Not configured"
                st.write(f"**API Key Status:** {api_status}")
                
                if not enrichment_status['api_key_configured']:
                    st.warning("⚠️ Together AI API key not configured. Set TOGETHER_API_KEY environment variable.")
                
                # Recommendations
                if enrichment_status.get('recommendations'):
                    st.subheader("💡 Recommendations")
                    for rec in enrichment_status['recommendations']:
                        st.info(f"• {rec}")
            
            with col2:
                st.subheader("🚀 Run Enrichment")
                
                # Enrichment settings
                with st.expander("⚙️ Settings"):
                    batch_size = st.slider("Batch Size", min_value=5, max_value=30, value=15, 
                                         help="Number of records to process at once")
                    max_batches = st.slider("Max Batches", min_value=1, max_value=20, value=10,
                                          help="Maximum number of batches to run")
                
                # Check if enrichment is needed
                needs_enrichment = enrichment_status['needs_enrichment']
                
                if not needs_enrichment:
                    st.success("✅ All data is already enriched!")
                    st.info("No missing company information, industries, or descriptions found.")
                else:
                    missing_total = enrichment_status['missing_data']['total']
                    st.info(f"📝 {missing_total} fields need enrichment")
                    
                    if not enrichment_status['api_key_configured']:
                        st.error("❌ Cannot run enrichment without API key")
                    else:
                        # Enrichment button
                        if st.button("🚀 Start Enrichment", type="primary", use_container_width=True):
                            # Show progress
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            results_container = st.container()
                            
                            status_text.text("🔄 Starting data enrichment...")
                            
                            # Run enrichment
                            enrichment_result = run_data_enrichment_for_app(
                                app_context="manual",
                                batch_size=batch_size,
                                max_batches=max_batches
                            )
                            
                            progress_bar.progress(1.0)
                            
                            if enrichment_result["success"]:
                                status_text.text("✅ Enrichment completed!")
                                
                                with results_container:
                                    st.success(enrichment_result["message"])
                                    
                                    if enrichment_result.get("stats"):
                                        improvements = enrichment_result["stats"]["improvements"]
                                        st.write("**Results:**")
                                        st.write(f"• Company names filled: {improvements['company']}")
                                        st.write(f"• Industries filled: {improvements['industry']}")
                                        st.write(f"• Descriptions filled: {improvements['description']}")
                                        st.write(f"• **Total fields enriched: {improvements['total']}**")
                                
                                # Refresh data
                                st.cache_data.clear()
                                time.sleep(2)
                                st.rerun()
                                
                            else:
                                status_text.text("❌ Enrichment failed")
                                with results_container:
                                    st.error(f"Enrichment failed: {enrichment_result.get('error', 'Unknown error')}")
                
                # Maintenance check
                st.divider()
                st.subheader("🔧 Maintenance")
                
                maintenance_check = quick_maintenance_check()
                if maintenance_check.get("needed", False):
                    st.warning("⚠️ Database maintenance recommended")
                    for reason in maintenance_check.get("reasons", []):
                        st.write(f"• {reason}")
                    
                    if st.button("🔧 Run Maintenance", use_container_width=True):
                        with st.spinner("Running maintenance..."):
                            maintenance_result = run_quick_maintenance()
                            if maintenance_result["success"]:
                                st.success("✅ Maintenance completed!")
                            else:
                                st.error(f"❌ Maintenance failed: {maintenance_result.get('error')}")
                else:
                    st.success("✅ Database is healthy")
                    health_score = maintenance_check.get("health_score", 0)
                    st.write(f"Health Score: {health_score:.2f}")

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: Use the sidebar to configure your search parameters before running the scraper.")
