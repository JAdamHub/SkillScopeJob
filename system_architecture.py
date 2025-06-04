from graphviz import Digraph
import os
import shutil

def check_graphviz_installation():
    """Check if Graphviz is installed and provide installation instructions"""
    if shutil.which('dot') is None:
        print("❌ Graphviz not found!")
        print("\n🔧 To install Graphviz:")
        print("  macOS:   brew install graphviz")
        print("  Ubuntu:  sudo apt-get install graphviz")
        print("  Windows: Download from https://graphviz.org/download/")
        print("\n💡 Alternative: I'll generate .dot files you can view online at:")
        print("     https://dreampuf.github.io/GraphvizOnline/")
        return False
    return True

def safe_render(dot_graph, filename, format='png'):
    """Safely render diagram with fallback options"""
    try:
        if check_graphviz_installation():
            dot_graph.render(filename, format=format, cleanup=True)
            print(f"✅ Generated: {filename}.{format}")
            return True
    except Exception as e:
        print(f"❌ Rendering failed: {e}")
    
    # Fallback: save DOT source file
    try:
        dot_filename = f"{filename}.dot"
        with open(dot_filename, 'w') as f:
            f.write(dot_graph.source)
        print(f"💾 Saved DOT source: {dot_filename}")
        print(f"   📖 View online at: https://dreampuf.github.io/GraphvizOnline/")
        return False
    except Exception as e:
        print(f"❌ Failed to save DOT file: {e}")
        return False

def create_simplified_architecture():
    """Create a simplified, clean system architecture diagram"""
    
    dot = Digraph(comment='SkillScopeJob - Simplified Architecture')
    dot.attr(rankdir='TB', size='12,10', dpi='200')
    dot.attr('graph', fontname='Arial', fontsize='11', overlap='false')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='10')
    dot.attr('edge', fontname='Arial', fontsize='9')
    
    # Simple color scheme
    USER_COLOR = '#E3F2FD'        # Light blue
    APP_COLOR = '#E8F5E8'         # Light green  
    ENGINE_COLOR = '#FFF3E0'      # Light orange
    DATA_COLOR = '#F3E5F5'        # Light purple
    EXTERNAL_COLOR = '#F5F5F5'    # Light gray
    
    # User Layer
    dot.node('user', 'User\n• Upload CV\n• Set preferences\n• View results', 
             fillcolor=USER_COLOR, shape='ellipse')
    
    # Application Layer
    with dot.subgraph(name='cluster_app') as c:
        c.attr(label='Application Layer', style='rounded', color='#2E7D32')
        c.attr('node', fillcolor=APP_COLOR)
        
        c.node('streamlit_ui', 'Streamlit Interface\n• File upload\n• Profile forms\n• Results display')
        c.node('cv_processor', 'CV Processor\n• Extract text\n• Parse skills\n• Create profile')
    
    # Core Engine
    with dot.subgraph(name='cluster_engine') as c:
        c.attr(label='Core Matching Engine', style='rounded', color='#F57C00')
        c.attr('node', fillcolor=ENGINE_COLOR)
        
        c.node('job_matcher', 'Job Matcher\n• Search jobs\n• Score relevance\n• Rank results')
        c.node('job_scraper', 'Job Scraper\n• Collect job data\n• Remove duplicates\n• Store in database')
    
    # Data & AI Layer
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='Data & Intelligence', style='rounded', color='#7B1FA2')
        c.attr('node', fillcolor=DATA_COLOR)
        
        c.node('database', 'SQLite Database\n• Job postings\n• User profiles\n• Auto-cleanup')
        c.node('ai_enrichment', 'AI Enrichment\n• Company info\n• Industry classification\n• Data enhancement')
    
    # External Services
    with dot.subgraph(name='cluster_external') as c:
        c.attr(label='External Services', style='rounded', color='#455A64')
        c.attr('node', fillcolor=EXTERNAL_COLOR)
        
        c.node('indeed', 'Indeed API\n• Job listings\n• Company data', shape='ellipse')
        c.node('together_ai', 'Together AI\n• LLM processing\n• Text analysis', shape='ellipse')
    
    # Main data flow - with complete user interaction loop
    dot.edge('user', 'streamlit_ui', label='interacts', color='#1976D2')
    dot.edge('streamlit_ui', 'cv_processor', label='CV file', color='#2E7D32')
    dot.edge('cv_processor', 'job_matcher', label='profile', color='#2E7D32')
    dot.edge('job_matcher', 'job_scraper', label='search request', color='#F57C00')
    dot.edge('job_scraper', 'indeed', label='scrape', color='#F57C00', style='dashed')
    dot.edge('job_scraper', 'database', label='store jobs', color='#F57C00')
    dot.edge('database', 'ai_enrichment', label='raw data', color='#7B1FA2')
    dot.edge('ai_enrichment', 'together_ai', label='API calls', color='#7B1FA2', style='dashed')
    dot.edge('ai_enrichment', 'database', label='enriched data', color='#7B1FA2')
    dot.edge('job_matcher', 'database', label='query jobs', color='#F57C00')
    
    # Complete the user feedback loop - this was missing!
    dot.edge('job_matcher', 'streamlit_ui', label='ranked results', color='#2E7D32')
    dot.edge('streamlit_ui', 'user', label='displays matches', color='#1976D2')
    
    return dot

def create_enhanced_data_flow():
    """Create enhanced data flow showing AI evaluation step"""
    
    dot = Digraph(comment='SkillScopeJob - Enhanced Data Flow')
    dot.attr(rankdir='LR', size='16,6')
    dot.attr('node', shape='ellipse', style='filled', fontsize='10')
    
    # Sequential flow with AI evaluation
    steps = [
        ('upload', 'CV Upload', '#E3F2FD'),
        ('extract', 'Extract Skills', '#E8F5E8'),
        ('search', 'Search Jobs', '#FFF3E0'),
        ('enrich', 'AI Enhance', '#F3E5F5'),
        ('evaluate', 'AI Evaluate', '#FFE0B2'),  # NEW step
        ('rank', 'Intelligent Rank', '#FFE0B2'),  # Enhanced step
        ('display', 'Show Results', '#E3F2FD')
    ]
    
    # Add nodes with enhanced descriptions
    enhanced_labels = {
        'upload': '1. CV Upload\n(PDF/DOC)',
        'extract': '2. Extract Skills\n(Parse & Structure)',
        'search': '3. Search Jobs\n(Scrape & Store)',
        'enrich': '4. AI Enhance\n(Company Info)',
        'evaluate': '5. AI Evaluate\n(Match Analysis)',
        'rank': '6. Intelligent Rank\n(Personalized)',
        'display': '7. Show Results\n(Insights + Jobs)'
    }
    
    for i, (node_id, _, color) in enumerate(steps):
        label = enhanced_labels.get(node_id, f"{i+1}. {steps[i][1]}")
        dot.node(node_id, label, fillcolor=color)
    
    # Connect sequentially with descriptive labels
    connections = [
        ('upload', 'extract', 'user data'),
        ('extract', 'search', 'search criteria'),
        ('search', 'enrich', 'raw jobs'),
        ('enrich', 'evaluate', 'enriched data'),
        ('evaluate', 'rank', 'match scores'),
        ('rank', 'display', 'final results')
    ]
    
    for source, target, label in connections:
        dot.edge(source, target, label=label)
    
    return dot

def create_ai_evaluation_detail():
    """Create detailed view of AI evaluation component"""
    
    dot = Digraph(comment='SkillScopeJob - AI Evaluation Detail')
    dot.attr(rankdir='TB', size='10,8')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Input sources
    dot.node('user_profile', 'User Profile\n• Skills\n• Experience\n• Preferences', fillcolor='#E8F5E8')
    dot.node('enriched_jobs', 'Enriched Jobs\n• Company info\n• Industry data\n• Job descriptions', fillcolor='#F3E5F5')
    
    # AI Evaluation components
    dot.node('skill_matcher', 'Skill Matching\n• Skill alignment\n• Gap identification\n• Proficiency analysis', fillcolor='#FFE0B2')
    dot.node('compatibility_scorer', 'Compatibility Scoring\n• Experience match\n• Culture fit\n• Growth potential', fillcolor='#FFE0B2')
    dot.node('recommendation_engine', 'Recommendation Engine\n• Personalized insights\n• Application tips\n• Skill suggestions', fillcolor='#FFE0B2')
    
    # AI Service
    dot.node('llm_api', 'Together AI LLM\n• Llama 3.3 70B\n• Advanced reasoning', fillcolor='#F5F5F5', shape='ellipse')
    
    # Output
    dot.node('intelligent_results', 'Intelligent Results\n• Ranked matches\n• Match explanations\n• Actionable insights', fillcolor='#E3F2FD')
    
    # Connections
    dot.edge('user_profile', 'skill_matcher', label='skills data')
    dot.edge('enriched_jobs', 'skill_matcher', label='job requirements')
    dot.edge('skill_matcher', 'compatibility_scorer', label='skill scores')
    dot.edge('user_profile', 'compatibility_scorer', label='profile data')
    dot.edge('enriched_jobs', 'compatibility_scorer', label='job context')
    dot.edge('compatibility_scorer', 'recommendation_engine', label='compatibility data')
    
    # AI API calls
    dot.edge('skill_matcher', 'llm_api', label='analysis requests', style='dashed')
    dot.edge('compatibility_scorer', 'llm_api', label='scoring requests', style='dashed')
    dot.edge('recommendation_engine', 'llm_api', label='insight generation', style='dashed')
    
    # Final output
    dot.edge('recommendation_engine', 'intelligent_results', label='final insights')
    
    return dot

def create_layered_architecture():
    """Create a clean layered architecture view. All descriptions are in English."""
    
    dot = Digraph(comment='SkillScopeJob - Layered Architecture')
    dot.attr(rankdir='TB', size='14,12', dpi='200') # Adjusted size
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    dot.attr('edge', fontsize='9')
    
    # Layer colors
    PRESENTATION_COLOR = '#E3F2FD' # Light Blue
    APPLICATION_SERVICE_COLOR = '#E8F5E8' # Light Green
    CORE_DOMAIN_COLOR = '#FFF3E0' # Light Orange
    DATA_ACCESS_COLOR = '#E0F2F1' # Light Teal
    EXTERNAL_INTEGRATION_COLOR = '#F3E5F5' # Light Purple
    DATABASE_COLOR = '#D7CCC8' # Light Brown

    # Presentation Layer
    with dot.subgraph(name='cluster_presentation') as c:
        c.attr(label='Presentation Layer', style='rounded', color='#1976D2')
        c.attr('node', fillcolor=PRESENTATION_COLOR)
        c.node('streamlit_ui', 'Streamlit UI (streamlit_cv_extraction.py)\\n\\n• User Interaction & Input\\n• CV Upload & Profile Forms\\n• Results & Insights Display')

    # Application Service Layer
    with dot.subgraph(name='cluster_application_service') as c:
        c.attr(label='Application Service Layer', style='rounded', color='#388E3C')
        c.attr('node', fillcolor=APPLICATION_SERVICE_COLOR)
        c.node('cv_extraction_service', 'CV Extraction Service (cv_extraction.py)\\n\\n• Orchestrates CV parsing via LLM')
        c.node('job_matching_service', 'Job Matching Service (profile_job_matcher.py)\\n\\n• Orchestrates profile-to-job matching\\n• Handles live scraping & DB fallback logic')
        c.node('cv_evaluation_service', 'CV Evaluation Service (cv_job_evaluator.py)\\n\\n• Orchestrates CV vs. job analysis via LLM')
        c.node('data_enrichment_service', 'Data Enrichment Service (data_enrichment_crew.py)\\n\\n• Orchestrates job data enrichment via CrewAI')

    # Core Domain / Business Logic Layer (Conceptual - logic is within services for this scale)
    # For a larger system, this might be more distinct.
    # Here, the "service" files contain significant core logic.
    # We can represent key algorithmic parts or specific responsibilities.
    with dot.subgraph(name='cluster_core_domain') as c:
        c.attr(label='Core Domain Logic (Embedded in Services)', style='rounded', color='#F57C00')
        c.attr('node', fillcolor=CORE_DOMAIN_COLOR)
        c.node('profile_management', 'User Profile Management\\n\\n(Logic in profile_job_matcher.py, database_models.py)\\n• Storing, Retrieving User Profiles')
        c.node('relevance_scoring', 'Relevance Scoring Logic\\n\\n(Logic in profile_job_matcher.py)\\n• Algorithm for job match scores')
        c.node('job_data_handling', 'Job Data Handling\\n\\n(Logic in indeed_scraper.py, data_enrichment_crew.py)\\n• Cleaning, Normalizing Job Data')

    # Data Access Layer
    with dot.subgraph(name='cluster_data_access') as c:
        c.attr(label='Data Access Layer', style='rounded', color='#00796B')
        c.attr('node', fillcolor=DATA_ACCESS_COLOR)
        c.node('orm_models', 'SQLAlchemy ORM (database_models.py)\\n\\n• Defines Data Models (JobPosting, UserProfile)\\n• Handles DB Session & Engine Setup')
        c.node('raw_db_access', 'SQLite Database (indeed_jobs.db)\\n\\n• Physical data storage', fillcolor=DATABASE_COLOR, shape='cylinder')

    # External Integration Layer
    with dot.subgraph(name='cluster_external_integration') as c:
        c.attr(label='External Integration Layer', style='rounded', color='#7B1FA2')
        c.attr('node', fillcolor=EXTERNAL_INTEGRATION_COLOR)
        c.node('indeed_integration', 'Indeed Integration (indeed_scraper.py via JobSpy)\\n\\n• Interface for scraping Indeed.com')
        c.node('together_ai_integration', 'Together AI LLM Integration\\n\\n(cv_extraction.py, cv_job_evaluator.py, data_enrichment_crew.py)\\n• Interface for Llama 3.x models')
        c.node('crewai_integration', 'CrewAI Integration (data_enrichment_crew.py)\\n\\n• AI Agent framework for enrichment tasks')

    # Layer connections (High-level)
    dot.edge('streamlit_ui', 'cv_extraction_service', label='CV data')
    dot.edge('streamlit_ui', 'job_matching_service', label='profile data / search commands')
    dot.edge('streamlit_ui', 'cv_evaluation_service', label='evaluation requests')

    dot.edge('cv_extraction_service', 'together_ai_integration', label='LLM calls')
    dot.edge('cv_extraction_service', 'profile_management', label='updates profile (conceptually)') 

    dot.edge('job_matching_service', 'profile_management', label='uses profile')
    dot.edge('job_matching_service', 'relevance_scoring', label='calculates scores')
    dot.edge('job_matching_service', 'indeed_integration', label='gets live jobs')
    dot.edge('job_matching_service', 'orm_models', label='accesses DB jobs/profiles')

    dot.edge('cv_evaluation_service', 'profile_management', label='uses profile')
    dot.edge('cv_evaluation_service', 'orm_models', label='accesses DB jobs/evals')
    dot.edge('cv_evaluation_service', 'together_ai_integration', label='LLM calls')

    dot.edge('data_enrichment_service', 'job_data_handling', label='processes jobs')
    dot.edge('data_enrichment_service', 'orm_models', label='updates DB jobs')
    dot.edge('data_enrichment_service', 'crewai_integration', label='uses AI agents')
    dot.edge('crewai_integration', 'together_ai_integration', label='uses LLMs (via CrewAI)', style='dashed')

    dot.edge('profile_management', 'orm_models', label='uses ORM')
    dot.edge('relevance_scoring', 'orm_models', label='uses job data from ORM (conceptually)')
    dot.edge('job_data_handling', 'orm_models', label='uses ORM')
    
    dot.edge('orm_models', 'raw_db_access', label='maps to/from')
    dot.edge('indeed_integration', 'job_data_handling', label='provides raw jobs')

    # Feedback to UI
    dot.edge('job_matching_service', 'streamlit_ui', label='matched jobs')
    dot.edge('cv_evaluation_service', 'streamlit_ui', label='evaluation insights')

    return dot

def create_user_journey_flow():
    """Create a user-centric journey flow diagram"""
    
    dot = Digraph(comment='SkillScopeJob - User Journey')
    dot.attr(rankdir='LR', size='16,8', dpi='200')
    dot.attr('node', shape='ellipse', style='filled', fontsize='10')
    
    # User journey steps with descriptions
    journey_steps = [
        ('start', 'User Starts\n\n• Has CV\n• Seeks Jobs', '#FFCDD2'),
        ('upload', 'Upload CV\n\n• PDF/Word\n• Personal Info', '#E3F2FD'),
        ('analyze', 'AI Analyzes CV\n\n• Extract Skills\n• Parse Experience', '#E8F5E8'),
        ('search', 'System Searches\n\n• Scrape Job Sites\n• Match Criteria', '#FFF3E0'),
        ('enhance', 'AI Enhances Data\n\n• Company Info\n• Industry Details', '#F3E5F5'),
        ('match', 'Smart Matching\n\n• Score Relevance\n• Rank Results', '#E8F5E8'),
        ('results', 'Show Results\n\n• Job Listings\n• Match Scores', '#E3F2FD'),
        ('apply', 'User Applies\n\n• Informed Decision\n• Better Matches', '#C8E6C9')
    ]
    
    # Add nodes
    for i, (node_id, label, color) in enumerate(journey_steps):
        dot.node(node_id, label, fillcolor=color)
    
    # Connect journey steps
    journey_connections = [
        ('start', 'upload', 'uploads CV'),
        ('upload', 'analyze', 'AI processing'),
        ('analyze', 'search', 'profile created'),
        ('search', 'enhance', 'raw job data'),
        ('enhance', 'match', 'enriched data'),
        ('match', 'results', 'ranked jobs'),
        ('results', 'apply', 'user decision')
    ]
    
    for source, target, label in journey_connections:
        dot.edge(source, target, label=label)
    
    return dot

def create_technology_stack():
    """Create a technology stack view"""
    
    dot = Digraph(comment='SkillScopeJob - Technology Stack')
    dot.attr(rankdir='TB', size='10,12', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Frontend Stack
    with dot.subgraph(name='cluster_frontend') as c:
        c.attr(label='Frontend Technologies', style='rounded', color='#2196F3')
        c.attr('node', fillcolor='#E3F2FD')
        c.node('streamlit', 'Streamlit\n\nWeb Framework\nfor Python')
        c.node('html_css', 'HTML/CSS\n\nCustom Styling\n& Components')
    
    # Backend Stack
    with dot.subgraph(name='cluster_backend') as c:
        c.attr(label='Backend Technologies', style='rounded', color='#4CAF50')
        c.attr('node', fillcolor='#E8F5E8')
        c.node('python', 'Python 3.x\n\nCore Language\n& Logic')
        c.node('pandas', 'Pandas\n\nData Processing\n& Analysis')
        c.node('jobspy', 'JobSpy\n\nJob Scraping\nLibrary')
    
    # AI/ML Stack
    with dot.subgraph(name='cluster_ai') as c:
        c.attr(label='AI/ML Technologies', style='rounded', color='#9C27B0')
        c.attr('node', fillcolor='#F3E5F5')
        c.node('together_ai', 'Together AI\n\nLLM API\n(Llama 3.3 70B)')
        c.node('langchain', 'LangChain\n\nLLM Framework\n& Integration')
        c.node('nlp', 'NLP Processing\n\nText Analysis\n& Extraction')
    
    # Data Stack
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='Data Technologies', style='rounded', color='#FF9800')
        c.attr('node', fillcolor='#FFF3E0')
        c.node('sqlite', 'SQLite\n\nLocal Database\n& Storage')
        c.node('json', 'JSON\n\nData Exchange\n& Config')
    
    # External APIs
    with dot.subgraph(name='cluster_apis') as c:
        c.attr(label='External APIs', style='rounded', color='#607D8B')
        c.attr('node', fillcolor='#ECEFF1')
        c.node('indeed_api', 'Indeed\n\nJob Board\nAPI/Scraping')
        c.node('pdf_lib', 'PDF Libraries\n\nDocument\nProcessing')
    
    # Technology relationships
    dot.edge('streamlit', 'python', label='built on')
    dot.edge('python', 'pandas', label='uses')
    dot.edge('python', 'jobspy', label='imports')
    dot.edge('python', 'langchain', label='integrates')
    dot.edge('langchain', 'together_ai', label='connects to')
    dot.edge('python', 'sqlite', label='queries')
    dot.edge('jobspy', 'indeed_api', label='scrapes')
    dot.edge('python', 'pdf_lib', label='processes with')
    
    return dot

def create_data_transformation_flow():
    """Create a data transformation focused diagram"""
    
    dot = Digraph(comment='SkillScopeJob - Data Transformation')
    dot.attr(rankdir='LR', size='16,6', dpi='200')
    dot.attr('node', shape='cylinder', style='filled', fontsize='10')
    
    # Data transformation stages
    transformations = [
        ('raw_cv', 'Raw CV\nDocument\n\n• PDF/Word\n• Unstructured', '#FFCDD2'),
        ('structured_cv', 'Structured\nCV Data\n\n• Parsed Text\n• Extracted Fields', '#E3F2FD'),
        ('user_profile', 'User Profile\n\n• Skills List\n• Preferences\n• Criteria', '#E8F5E8'),
        ('raw_jobs', 'Raw Job\nListings\n\n• Basic Info\n• Job Descriptions', '#FFF3E0'),
        ('enriched_jobs', 'Enriched Job\nData\n\n• Company Info\n• Industry Tags', '#F3E5F5'),
        ('matched_jobs', 'Matched &\nRanked Jobs\n\n• Relevance Scores\n• Personalized', '#E8F5E8'),
        ('final_results', 'Final Results\n\n• Top Matches\n• Insights\n• Recommendations', '#C8E6C9')
    ]
    
    # Add transformation nodes
    for node_id, label, color in transformations:
        dot.node(node_id, label, fillcolor=color)
    
    # Transformation processes (diamond shapes)
    dot.attr('node', shape='diamond', style='filled', fillcolor='#FFF8E1')
    dot.node('parse', 'Parse &\nExtract')
    dot.node('profile_build', 'Build\nProfile')
    dot.node('scrape', 'Scrape &\nCollect')
    dot.node('enrich', 'AI\nEnrich')
    dot.node('match_rank', 'Match &\nRank')
    dot.node('present', 'Format &\nPresent')
    
    # Data flow connections
    dot.edge('raw_cv', 'parse')
    dot.edge('parse', 'structured_cv')
    dot.edge('structured_cv', 'profile_build')
    dot.edge('profile_build', 'user_profile')
    dot.edge('user_profile', 'scrape')
    dot.edge('scrape', 'raw_jobs')
    dot.edge('raw_jobs', 'enrich')
    dot.edge('enrich', 'enriched_jobs')
    dot.edge('enriched_jobs', 'match_rank')
    dot.edge('user_profile', 'match_rank', style='dashed')
    dot.edge('match_rank', 'matched_jobs')
    dot.edge('matched_jobs', 'present')
    dot.edge('present', 'final_results')
    
    return dot

def create_component_interaction():
    """Create a component interaction focused diagram. All descriptions are in English."""
    
    dot = Digraph(comment='SkillScopeJob - Component Interactions')
    dot.attr(rankdir='TB', size='14,12', dpi='200') # Adjusted size
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    dot.attr('edge', fontsize='9', penwidth='2') # Make edges thicker and more visible
    
    # More distinct and vibrant colors
    UI_COLOR = '#1565C0' # Darker Blue - Streamlit
    CV_PROC_COLOR = '#2E7D32' # Darker Green - cv_extraction
    JOB_SCRAPE_COLOR = '#F57C00' # Darker Orange - indeed_scraper
    JOB_MATCH_COLOR = '#E65100' # Darker Deep Orange - profile_job_matcher
    AI_EVAL_COLOR = '#C62828' # Darker Red - cv_job_evaluator
    AI_ENRICH_COLOR = '#7B1FA2' # Darker Purple - data_enrichment_crew
    DB_MODEL_COLOR = '#00695C' # Darker Teal - database_models
    DB_FILE_COLOR = '#5D4037' # Darker Brown - indeed_jobs.db
    EXTERNAL_COLOR = '#37474F' # Darker Blue Grey - External Services

    # Core components with their primary Python file in parentheses - using lighter fill colors for better text readability
    dot.node('streamlit_ui', 'User Interface (streamlit_cv_extraction.py)\n\n• Handles CV Upload & Profile Input\n• Initiates Searches & Evaluations\n• Displays Results & Insights', 
             fillcolor='#E3F2FD', color=UI_COLOR, penwidth='2')
    
    dot.node('cv_extractor', 'CV Extractor (cv_extraction.py)\n\n• Parses CV (PDF/DOCX)\n• Extracts Skills, Experience, Education via LLM\n• Suggests Profile Data', 
             fillcolor='#E8F5E8', color=CV_PROC_COLOR, penwidth='2')
    
    dot.node('job_scraper_module', 'Job Scraper (indeed_scraper.py)\n\n• Scrapes Job Boards (e.g., Indeed via JobSpy)\n• Collects Raw Job Postings\n• Initial Storage/Update to DB (via ORM)', 
             fillcolor='#FFF3E0', color=JOB_SCRAPE_COLOR, penwidth='2')
    
    dot.node('data_enricher', 'AI Data Enricher (data_enrichment_crew.py)\n\n• Enhances Job Data (Company Info, Industry) via CrewAI & LLMs\n• Updates Job Postings in DB (Enrichment Status, Freshness)', 
             fillcolor='#F3E5F5', color=AI_ENRICH_COLOR, penwidth='2')
    
    dot.node('profile_matcher', 'Profile Job Matcher (profile_job_matcher.py)\n\n• Matches User Profile to Jobs (Live & DB)\n• Calculates Relevance Scores (User Profile Match)\n• Interacts with DB via SQLAlchemy ORM', 
             fillcolor='#FFE0B2', color=JOB_MATCH_COLOR, penwidth='2')

    dot.node('cv_evaluator_module', 'CV-Job Evaluator (cv_job_evaluator.py)\n\n• Analyzes CV against Job Descriptions via LLM\n• Provides Strengths, Gaps, Recommendations\n• Stores Evaluation Summaries (moving to ORM)',
             fillcolor='#FFCDD2', color=AI_EVAL_COLOR, penwidth='2')
    
    dot.node('database_abstraction', 'Data Models & DB Access (database_models.py)\n\n• SQLAlchemy ORM Definitions (JobPosting, UserProfile, etc.)\n• Database Engine & Session Management\n• Provides Abstraction Layer to DB', 
             fillcolor='#E0F2F1', color=DB_MODEL_COLOR, penwidth='2')
    
    dot.node('actual_database', 'SQLite Database (indeed_jobs.db)\n\n• Physical Data Storage for all application data\n(Job Postings, User Profiles, Evaluations)', 
             fillcolor='#EFEBE9', color=DB_FILE_COLOR, penwidth='2', shape='cylinder')

    dot.node('together_ai_service', 'Together AI (External LLM Service)\n\n• Provides Llama 3.x models for NLP tasks', 
             fillcolor='#ECEFF1', color=EXTERNAL_COLOR, penwidth='2', shape='ellipse')
    dot.node('indeed_com_service', 'Indeed.com (External Job Source)\n\n• Source of Job Postings Data', 
             fillcolor='#ECEFF1', color=EXTERNAL_COLOR, penwidth='2', shape='ellipse')
    
    # Interaction flows with clear labels and thicker, more visible edges
    dot.edge('streamlit_ui', 'cv_extractor', label='CV file for parsing', color=CV_PROC_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('cv_extractor', 'together_ai_service', label='LLM call for CV data', style='dashed', color=EXTERNAL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('cv_extractor', 'streamlit_ui', label='parsed CV data (suggestions)', color=UI_COLOR, penwidth='2', arrowsize='1.2') # Feedback loop

    dot.edge('streamlit_ui', 'profile_matcher', label='user profile data / search trigger', color=JOB_MATCH_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('profile_matcher', 'database_abstraction', label='store/fetch user profile, fetch jobs', color=DB_MODEL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('profile_matcher', 'job_scraper_module', label='trigger live scrape', color=JOB_SCRAPE_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('job_scraper_module', 'indeed_com_service', label='scrape request', style='dashed', color=EXTERNAL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('job_scraper_module', 'database_abstraction', label='store raw jobs', color=DB_MODEL_COLOR, penwidth='2', arrowsize='1.2')
    
    dot.edge('database_abstraction', 'actual_database', label='ORM operations (CRUD)', color=DB_FILE_COLOR, penwidth='3', arrowsize='1.3')

    dot.edge('data_enricher', 'database_abstraction', label='fetch raw jobs / update enriched jobs', color=DB_MODEL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('data_enricher', 'together_ai_service', label='LLM call for enrichment', style='dashed', color=EXTERNAL_COLOR, penwidth='2', arrowsize='1.2')
    # Implicit: data_enricher is likely triggered by a scheduler or manually, not directly from UI in primary flow

    dot.edge('streamlit_ui', 'cv_evaluator_module', label='job list & profile for evaluation', color=AI_EVAL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('cv_evaluator_module', 'database_abstraction', label='fetch user profile / store evaluation', color=DB_MODEL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('cv_evaluator_module', 'together_ai_service', label='LLM call for CV vs. Job analysis', style='dashed', color=EXTERNAL_COLOR, penwidth='2', arrowsize='1.2')
    dot.edge('cv_evaluator_module', 'streamlit_ui', label='evaluation results & insights', color=UI_COLOR, penwidth='2', arrowsize='1.2')

    dot.edge('profile_matcher', 'streamlit_ui', label='matched jobs & scores', color=UI_COLOR, penwidth='2', arrowsize='1.2')
    
    return dot

def create_simple_overview():
    """Create the simplest possible overview"""
    
    dot = Digraph(comment='SkillScopeJob - Simple Overview')
    dot.attr(rankdir='LR', size='14,6', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='12')
    
    # Three main components
    dot.node('input', 'INPUT\n\nUser uploads CV\n+\nSets preferences', fillcolor='#E3F2FD')
    dot.node('processing', 'PROCESSING\n\nAI analyzes CV\n+\nFinds matching jobs\n+\nEnhances with company data', fillcolor='#E8F5E8')
    dot.node('output', 'OUTPUT\n\nRanked job matches\n+\nRelevance scores\n+\nPersonalized insights', fillcolor='#FFF3E0')
    
    # Simple flow
    dot.edge('input', 'processing', label='User data', fontsize='11')
    dot.edge('processing', 'output', label='Smart results', fontsize='11')
    
    # Add external connections
    dot.node('job_sites', 'Job Sites\n(Indeed)', fillcolor='#F3E5F5', shape='ellipse')
    dot.node('ai_service', 'AI Service\n(Together AI)', fillcolor='#F3E5F5', shape='ellipse')
    
    dot.edge('processing', 'job_sites', label='scrapes', style='dashed', fontsize='10')
    dot.edge('processing', 'ai_service', label='enhances', style='dashed', fontsize='10')
    
    return dot

def create_file_based_architecture():
    """Create architecture diagram showing actual files and their relationships. All text is in English."""
    
    dot = Digraph(comment='SkillScopeJob - File-Based Architecture')
    dot.attr(rankdir='TB', size='18,14', dpi='200')
    dot.attr('graph', fontname='Arial', fontsize='12', overlap='false', splines='ortho')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='10')
    dot.attr('edge', fontname='Arial', fontsize='9')
    
    # Color scheme
    UI_COLOR = '#4CAF50'          # Green for UI files
    CV_PROCESSING_COLOR = '#2196F3' # Blue for CV processing
    JOB_PROCESSING_COLOR = '#FF9800' # Orange for Job processing/matching
    DATA_MGMT_COLOR = '#9C27B0'    # Purple for Data models/DB access
    DATABASE_FILE_COLOR = '#795548'# Brown for DB file
    AI_COLOR = '#00ACC1'          # Cyan for AI/LLM related
    CONFIG_COLOR = '#607D8B'      # Gray for config/ontology
    ADMIN_COLOR = '#E91E63'       # Pink for admin utilities
    
    # UI Layer
    with dot.subgraph(name='cluster_ui') as c:
        c.attr(label='🎨 User Interface & Entry Point', style='rounded', color=UI_COLOR, fontcolor=UI_COLOR)
        c.node('streamlit_cv_extraction_py', 'streamlit_cv_extraction.py\n\n• Main Streamlit Application UI\n• User Profile Input & Management\n• CV Upload & AI-Powered Parsing\n• Job Search Trigger & Results Display\n• CV-Job Evaluation Interface', 
               fillcolor=UI_COLOR + '30', color=UI_COLOR)

    # CV Processing & Extraction Layer
    with dot.subgraph(name='cluster_cv_proc') as c:
        c.attr(label='📄 CV Processing & AI Extraction', style='rounded', color=CV_PROCESSING_COLOR, fontcolor=CV_PROCESSING_COLOR)
        c.node('cv_extraction_py', 'cv_extraction.py\n\n• LLM-based CV Parsing (Together AI)\n• Extracts Skills, Experience, Education\n• Suggests Profile Fields & Keywords\n• Supports PDF, DOCX, TXT formats',
               fillcolor=CV_PROCESSING_COLOR + '30', color=CV_PROCESSING_COLOR)

    # Core Job Processing Layer
    with dot.subgraph(name='cluster_job_core') as c:
        c.attr(label='⚙️ Job Processing, Matching & Evaluation', style='rounded', color=JOB_PROCESSING_COLOR, fontcolor=JOB_PROCESSING_COLOR)
        c.node('indeed_scraper_py', 'indeed_scraper.py\n\n• Scrapes Job Data from Indeed.com (JobSpy)\n• Stores Job Postings via SQLAlchemy ORM\n• Handles URL Uniqueness & Data Cleaning\n• Auto-cleanup of Stale Jobs', 
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)
        c.node('profile_job_matcher_py', 'profile_job_matcher.py\n\n• Matches User Profiles to Jobs (DB + Live)\n• Uses SQLAlchemy ORM for All DB Operations\n• Calculates Relevance Scores & Rankings\n• Manages User Profile CRUD Operations',
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)
        c.node('cv_job_evaluator_py', 'cv_job_evaluator.py\n\n• AI-Powered CV vs Job Analysis (Together AI)\n• Detailed Match Feedback & Gap Analysis\n• Stores Evaluation Results via SQLAlchemy\n• Generates Improvement Recommendations',
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)

    # AI Data Enrichment Layer
    with dot.subgraph(name='cluster_enrich') as c:
        c.attr(label='🤖 AI Data Enrichment & Enhancement', style='rounded', color=AI_COLOR, fontcolor=AI_COLOR)
        c.node('data_enrichment_crew_py', 'data_enrichment_crew.py\n\n• Uses CrewAI Framework for Data Enhancement\n• Enriches Job Data (Company Info, Industry)\n• Updates Job Freshness & Enrichment Status\n• Manages Data Quality & Completeness',
               fillcolor=AI_COLOR + '30', color=AI_COLOR)

    # Data Models & Database Layer
    with dot.subgraph(name='cluster_data_models_db') as c:
        c.attr(label='💾 Data Models & Database Management', style='rounded', color=DATA_MGMT_COLOR, fontcolor=DATA_MGMT_COLOR)
        c.node('database_models_py', 'database_models.py\n\n• SQLAlchemy ORM Models & Table Definitions\n• JobPosting, UserProfile, CVJobEvaluation Models\n• Relationship Mappings & Database Engine Setup\n• Session Management & Auto-table Creation',
               fillcolor=DATA_MGMT_COLOR + '30', color=DATA_MGMT_COLOR)
        c.node('indeed_jobs_db', 'indeed_jobs.db\n\n• SQLite Database File\n• Stores All Application Data\n• Job Postings, User Profiles, Evaluations', 
               fillcolor=DATABASE_FILE_COLOR + '30', color=DATABASE_FILE_COLOR, shape='cylinder')

    # Admin Utilities Layer
    with dot.subgraph(name='cluster_admin') as c:
        c.attr(label='🔧 Administrative Utilities', style='rounded', color=ADMIN_COLOR, fontcolor=ADMIN_COLOR)
        c.node('debug_database_py', 'admin_utils/debug_database.py\n\n• Database Debugging & Inspection Tools\n• Data Verification & Cleanup Utilities',
               fillcolor=ADMIN_COLOR + '30', color=ADMIN_COLOR)
        c.node('admin_streamlit_app_py', 'admin_utils/streamlit_app.py\n\n• Administrative Web Interface\n• Database Management Tools',
               fillcolor=ADMIN_COLOR + '30', color=ADMIN_COLOR)

    # Configuration & Data Files
    with dot.subgraph(name='cluster_config_data') as c:
        c.attr(label='⚙️ Configuration & Reference Data', style='rounded', color=CONFIG_COLOR, fontcolor=CONFIG_COLOR)
        c.node('requirements_txt', 'requirements.txt\n\n• Python Package Dependencies\n• Version Specifications', 
               fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('readme_md', 'README.md\n\n• Project Documentation\n• Setup & Usage Instructions',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('skill_ontology_csv', 'skill_ontology.csv\n\n• Predefined Skills Database\n• Skill Categories & Classifications',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('roles_industries_ontology_csv', 'roles_industries_ontology.csv\n\n• Job Roles & Industries Reference\n• Career Path Classifications',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('user_profile_log_csv', 'advanced_user_profile_log.csv\n\n• User Profile Activity Logs\n• Search History & Analytics',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)

    # External Services
    with dot.subgraph(name='cluster_external_services') as c:
        c.attr(label='🌐 External Services & APIs', style='rounded', color='#D32F2F', fontcolor='#D32F2F')
        c.node('indeed_service', 'Indeed.com\n\n• Source for Job Listings\n• Scraped via JobSpy Library', 
               fillcolor='#FFEBEE', color='#D32F2F', shape='ellipse')
        c.node('together_ai_service', 'Together AI API\n\n• LLM Services (Llama 3.x Models)\n• CV Parsing & Job Evaluation\n• Company Data Enrichment', 
               fillcolor='#FFEBEE', color='#D32F2F', shape='ellipse')

    # --- Core Application Flow Relationships ---

    # Main UI to Processing Modules
    dot.edge('streamlit_cv_extraction_py', 'cv_extraction_py', label='triggers CV parsing', color=CV_PROCESSING_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'profile_job_matcher_py', label='triggers job search & profile storage', color=JOB_PROCESSING_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'cv_job_evaluator_py', label='triggers CV evaluation', color=JOB_PROCESSING_COLOR)

    # CV Processing Flows
    dot.edge('cv_extraction_py', 'together_ai_service', label='LLM API calls for CV parsing', style='dashed', color=AI_COLOR)
    dot.edge('cv_extraction_py', 'database_models_py', label='uses UserProfile model structure', style='dotted', color=DATA_MGMT_COLOR)

    # Job Processing Core Flows
    dot.edge('indeed_scraper_py', 'indeed_service', label='scrapes job data', style='dashed', color=JOB_PROCESSING_COLOR)
    dot.edge('indeed_scraper_py', 'database_models_py', label='uses JobPosting model', color=DATA_MGMT_COLOR)
    
    dot.edge('profile_job_matcher_py', 'database_models_py', label='full SQLAlchemy ORM operations', color=DATA_MGMT_COLOR)
    dot.edge('profile_job_matcher_py', 'indeed_scraper_py', label='triggers live job scraping', color=JOB_PROCESSING_COLOR)

    dot.edge('cv_job_evaluator_py', 'database_models_py', label='uses UserProfile & CVJobEvaluation models', color=DATA_MGMT_COLOR)
    dot.edge('cv_job_evaluator_py', 'together_ai_service', label='LLM API calls for evaluation', style='dashed', color=AI_COLOR)

    # Data Enrichment Flows
    dot.edge('data_enrichment_crew_py', 'database_models_py', label='updates JobPosting enrichment data', color=DATA_MGMT_COLOR)
    dot.edge('data_enrichment_crew_py', 'together_ai_service', label='LLM API calls for enrichment', style='dashed', color=AI_COLOR)

    # Database Core Connection
    dot.edge('database_models_py', 'indeed_jobs_db', label='SQLAlchemy ORM operations', color=DATABASE_FILE_COLOR)
    
    # Configuration & Reference Data Usage
    dot.edge('streamlit_cv_extraction_py', 'skill_ontology_csv', label='loads skill references', style='dotted', color=CONFIG_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'roles_industries_ontology_csv', label='loads role references', style='dotted', color=CONFIG_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'user_profile_log_csv', label='logs user activities', style='dotted', color=CONFIG_COLOR)

    # Admin Utilities Access
    dot.edge('debug_database_py', 'indeed_jobs_db', label='direct database inspection', style='dashed', color=ADMIN_COLOR)
    dot.edge('admin_streamlit_app_py', 'database_models_py', label='admin interface to data models', style='dashed', color=ADMIN_COLOR)
    
    return dot

def create_module_dependency_diagram():
    """Create a module dependency diagram showing imports and relationships.
    All descriptions and labels are in English.
    """
    
    dot = Digraph(comment='SkillScopeJob - Module Dependencies')
    dot.attr(rankdir='LR', size='20,14', dpi='200') # Increased size
    dot.attr('node', shape='box', style='rounded,filled', fontsize='9') # Smaller font for more text
    dot.attr('edge', fontsize='8')

    # Python modules with their dependencies (actual filenames from the project)
    modules = {
        'streamlit_cv_extraction.py': {
            'imports': ['streamlit', 'cv_extraction.py', 'profile_job_matcher.py', 'cv_job_evaluator.py', 'os', 'uuid', 'csv', 'json', 'logging', 'datetime'],
            'color': '#4CAF50', # Green for UI
            'description': 'Main Streamlit Application UI\\n\\n• Handles user input (CV, profile)\\n• Triggers processing (CV parsing, job matching, evaluation)\\n• Displays results to the user'
        },
        'cv_extraction.py': {
            'imports': ['langchain_together', 'PyPDF2', 'docx', 'python-docx', 'logging', 'os', 're', 'database_models.py'], # python-docx might be imported as docx
            'color': '#2196F3', # Blue for CV processing
            'description': 'CV Parsing Engine\\n\\n• Uses LLM (TogetherAI via langchain) to parse CVs\\n• Extracts skills, experience, education, etc.\\n• Populates/suggests profile fields'
        },
        'profile_job_matcher.py': {
            'imports': ['sqlalchemy', 'database_models.py', 'indeed_scraper.py', 'datetime', 'logging', 'json'],
            'color': '#FF9800', # Orange for Job matching
            'description': 'Job Matching Engine\\n\\n• Matches user profiles to job postings (DB & Live)\\n• Uses SQLAlchemy for ORM-based database interactions\\n• Calculates relevance scores, updates DB'
        },
        'indeed_scraper.py': {
            'imports': ['jobspy', 'sqlite3', 'database_models.py', 'datetime', 'logging', 'json', 'requests', 'bs4'], # bs4 for potential direct parsing if jobspy has pass-through
            'color': '#FF9800', # Orange for Job scraping
            'description': 'Job Scraping Engine\\n\\n• Scrapes job data (e.g., from Indeed via jobspy)\\n• Stores/updates job postings in DB (via SQLAlchemy models)\\n• Handles data cleaning and initial storage'
        },
        'cv_job_evaluator.py': {
            'imports': ['langchain_together', 'database_models.py', 'sqlalchemy', 'logging', 'json', 'datetime', 'os', 're'],
            'color': '#00ACC1', # Cyan for AI Evaluation
            'description': 'CV vs. Job Evaluation Engine\\n\\n• Uses LLM (TogetherAI) to analyze CV against job descriptions\\n• Provides detailed match feedback (strengths, gaps)\\n• Stores evaluation results (moving to SQLAlchemy)'
        },
        'data_enrichment_crew.py': {
            'imports': ['crewai', 'langchain_community', 'database_models.py', 'sqlalchemy', 'logging', 'datetime', 'os', 'json', 'requests'], # Assuming CrewAI uses langchain_community or similar
            'color': '#00ACC1', # Cyan for AI Enrichment
            'description': 'Job Data Enrichment Engine\\n\\n• Uses CrewAI (with LLMs) to enrich job data\\n• Finds company info, industry, logo, etc.\\n• Updates job_postings table (enrichment_status, job_freshness)'
        },
        'database_models.py': {
            'imports': ['sqlalchemy', 'enum', 'datetime', 'json'],
            'color': '#9C27B0', # Purple for Data models
            'description': 'Database Models & Schema\\n\\n• Defines SQLAlchemy ORM models (JobPosting, UserProfile, etc.)\\n• Manages table schemas, relationships, and DB engine setup (SessionLocal)'
        },
        # Removed config.py as it's not a central explicit module, .env is used for keys
        # Removed ui_components.py as its logic is mostly within streamlit_cv_extraction.py for this project
        # Removed main.py as streamlit_cv_extraction.py is the runnable UI
    }
    
    # Add module nodes
    for module_filename, info in modules.items():
        # Node ID should be filename without .py for graphviz
        node_id = module_filename.replace('.py', '')
        dot.node(node_id, f"{module_filename}\\n\\n{info['description']}", 
                 fillcolor=f"{info['color']}20", color=info['color']) # Light fill
    
    # Add dependency edges (module to module)
    for module_filename, info in modules.items():
        source_node_id = module_filename.replace('.py', '')
        for imported_filename in info['imports']:
            # Check if the import is another module in our list
            if imported_filename in modules:
                target_node_id = imported_filename.replace('.py', '')
                dot.edge(source_node_id, target_node_id, label='imports', color=info['color'], style='dashed', fontsize='7')
            elif imported_filename.endswith('.py') and imported_filename not in modules:
                # If it's a .py file but not in our core list (e.g. a utility not yet added), note it
                pass # Or add a generic "utils" node if many such exist

    # Add key external library dependencies (as conceptual nodes)
    external_libs = {
        'streamlit': {'color': '#FF4B4B', 'desc': 'Web Framework'},
        'sqlalchemy': {'color': '#75A5C0', 'desc': 'ORM & SQL Toolkit'},
        'langchain_together': {'color': '#F06A30', 'desc': 'LLM Integration (TogetherAI)'}, # Specific for TogetherAI
        'jobspy': {'color': '#D4A017', 'desc': 'Job Scraping Library'},
        'crewai': {'color': '#4C8BF5', 'desc': 'AI Agent Framework'},
        'PyPDF2': {'color': '#A0522D', 'desc': 'PDF Processing'},
        'python-docx': {'color': '#2A5699', 'desc': 'DOCX Processing'}, # or 'docx'
        'requests': {'color': '#008080', 'desc': 'HTTP Requests'},
        'beautifulsoup4': {'color': '#E9967A', 'desc': 'HTML/XML Parsing (bs4)'}, # often used with scrapers
        'dotenv': {'color': '#C9A0DC', 'desc': 'Environment Variables (.env)'},
        # 'pandas', 'numpy' can be added if their usage is widespread and critical for a module
    }
    
    for lib_name, lib_info in external_libs.items():
        dot.node(lib_name, f"{lib_name}\\n({lib_info['desc']})", 
                 fillcolor=f"{lib_info['color']}20", color=lib_info['color'], shape='ellipse', fontsize='8')

    # Connect modules to their key external libraries
    module_to_external_deps = {
        'streamlit_cv_extraction.py': ['streamlit'],
        'cv_extraction.py': ['langchain_together', 'PyPDF2', 'python-docx', 'dotenv'],
        'profile_job_matcher.py': ['sqlalchemy', 'jobspy', 'requests'], # jobspy for indeed_scraper call, requests if direct calls
        'indeed_scraper.py': ['jobspy', 'sqlalchemy', 'requests', 'beautifulsoup4'], # bs4 if jobspy allows passing parsed content or direct use
        'cv_job_evaluator.py': ['langchain_together', 'sqlalchemy', 'dotenv'],
        'data_enrichment_crew.py': ['crewai', 'sqlalchemy', 'requests', 'dotenv'], # CrewAI uses langchain typically
        'database_models.py': ['sqlalchemy'],
    }

    for module_filename, ext_deps in module_to_external_deps.items():
        source_node_id = module_filename.replace('.py', '')
        if source_node_id in [m.replace('.py','') for m in modules.keys()]: # Check if module exists
            for ext_lib_name in ext_deps:
                if ext_lib_name in external_libs:
                    dot.edge(source_node_id, ext_lib_name, label='uses', 
                             color=external_libs[ext_lib_name]['color'], style='dotted', fontsize='7')
    
    return dot

def create_application_flow_with_files():
    """Create application flow showing file execution order and data flow"""
    
    dot = Digraph(comment='SkillScopeJob - Application Flow with Files')
    dot.attr(rankdir='TB', size='14,16', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Execution phases with actual files from the project
    phases = [
        {
            'name': 'initialization',
            'label': '🚀 INITIALIZATION PHASE',
            'files': [
                ('streamlit_start', 'streamlit_cv_extraction.py\nLaunches Streamlit app', '#E3F2FD'),
                ('db_init', 'database_models.py\nInitializes SQLAlchemy models', '#F3E5F5'),
                ('ontology_load', 'Load skill_ontology.csv &\nroles_industries_ontology.csv', '#ECEFF1')
            ]
        },
        {
            'name': 'user_interaction',
            'label': '👤 USER INTERACTION PHASE',
            'files': [
                ('ui_render', 'Streamlit UI renders\nCV upload & profile forms', '#E8F5E8'),
                ('file_upload', 'User uploads CV file\n(PDF/DOCX/TXT)', '#FFF9C4'),
                ('profile_input', 'User enters preferences\n& search criteria', '#FFF9C4')
            ]
        },
        {
            'name': 'cv_processing',
            'label': '📄 CV PROCESSING PHASE',
            'files': [
                ('cv_parse', 'cv_extraction.py\nParses CV via Together AI LLM', '#FFF3E0'),
                ('skill_extract', 'Extract skills, experience,\neducation from CV text', '#FFF3E0'),
                ('profile_save', 'database_models.py\nSaves UserProfile via ORM', '#F3E5F5')
            ]
        },
        {
            'name': 'job_search',
            'label': '🔍 JOB SEARCH PHASE',
            'files': [
                ('job_scrape', 'indeed_scraper.py\nScrapes Indeed via JobSpy', '#FFEBEE'),
                ('indeed_api', 'Indeed.com\nJob listings data source', '#FFCDD2'),
                ('job_store', 'database_models.py\nStores JobPosting via ORM', '#F3E5F5')
            ]
        },
        {
            'name': 'ai_enhancement',
            'label': '🤖 AI ENHANCEMENT PHASE',
            'files': [
                ('ai_process', 'data_enrichment_crew.py\nEnhances job data via CrewAI', '#F3E5F5'),
                ('together_ai', 'Together AI LLM\nCompany & industry enrichment', '#E1F5FE'),
                ('data_update', 'Updates job enrichment status\nin indeed_jobs.db', '#F3E5F5')
            ]
        },
        {
            'name': 'matching_evaluation',
            'label': '🎯 MATCHING & EVALUATION PHASE',
            'files': [
                ('job_match', 'profile_job_matcher.py\nMatches profile to jobs', '#E8F5E8'),
                ('cv_evaluate', 'cv_job_evaluator.py\nEvaluates CV vs jobs via LLM', '#E1F5FE'),
                ('final_results', 'streamlit_cv_extraction.py\nDisplays ranked results & insights', '#E8F5E8')
            ]
        }
    ]
    
    # Create phase clusters
    prev_phase_files = []
    for phase in phases:
        with dot.subgraph(name=f'cluster_{phase["name"]}') as c:
            c.attr(label=phase['label'], style='rounded', fontsize='12')
            
            phase_files = []
            for file_id, file_label, color in phase['files']:
                c.node(file_id, file_label, fillcolor=color)
                phase_files.append(file_id)
            
            # Connect files within phase
            for i in range(len(phase_files) - 1):
                dot.edge(phase_files[i], phase_files[i + 1], style='bold')
            
            # Connect to previous phase
            if prev_phase_files:
                dot.edge(prev_phase_files[-1], phase_files[0], color='red', style='bold')
            
            prev_phase_files = phase_files
    
    return dot

def create_repository_structure_view():
    """Create a visual representation of the actual project repository structure"""
    
    dot = Digraph(comment='SkillScopeJob - Repository Structure')
    dot.attr(rankdir='TB', size='12,14', dpi='200')
    dot.attr('node', shape='folder', style='filled', fontsize='10')
    
    # Root folder
    dot.node('root', 'SkillScopeJob/\n📁 Root Directory', fillcolor='#FFF3E0')
    
    # Main application files (actual files from project)
    dot.node('app_files', '📄 Core Application Files\n\n• streamlit_cv_extraction.py (Main UI)\n• cv_extraction.py (CV Processing)\n• profile_job_matcher.py (Job Matching)\n• cv_job_evaluator.py (AI Evaluation)\n• indeed_scraper.py (Job Scraping)\n• data_enrichment_crew.py (AI Enrichment)', 
             fillcolor='#E3F2FD', shape='box')
    
    # Data and database files (actual files)
    dot.node('data_files', '💾 Data & Database Files\n\n• database_models.py (SQLAlchemy ORM)\n• indeed_jobs.db (SQLite Database)\n• skill_ontology.csv (Skills Reference)\n• roles_industries_ontology.csv (Roles Reference)\n• advanced_user_profile_log.csv (User Logs)', 
             fillcolor='#F3E5F5', shape='box')
    
    # Configuration files (actual files)
    dot.node('config_files', '⚙️ Configuration Files\n\n• requirements.txt (Dependencies)\n• README.md (Documentation)\n• system_architecture.py (This file)', 
             fillcolor='#ECEFF1', shape='box')
    
    # Admin utilities (actual directory)
    dot.node('admin_files', '🔧 Admin Utilities\n\n• admin_utils/debug_database.py\n• admin_utils/streamlit_app.py', 
             fillcolor='#FFEBEE', shape='box')
    
    # Runtime and cache files (actual directories)
    dot.node('runtime_files', '📝 Runtime & Cache Files\n\n• __pycache__/ (Python Cache)\n• cache/ (Application Cache)\n• *.log (Log Files)\n• *.png (Generated Diagrams)', 
             fillcolor='#F5F5F5', shape='box')
    
    # Connect to root
    for node in ['app_files', 'data_files', 'config_files', 'admin_files', 'runtime_files']:
        dot.edge('root', node)
    
    # Show relationships between file groups
    dot.edge('app_files', 'data_files', label='uses ORM & data', style='dashed')
    dot.edge('app_files', 'config_files', label='reads config', style='dashed')
    dot.edge('admin_files', 'data_files', label='manages DB', style='dashed')
    dot.edge('app_files', 'runtime_files', label='generates logs/cache', style='dotted')
    
    return dot

def create_comprehensive_system_overview():
    """Create the most comprehensive system overview with actual project files"""
    
    dot = Digraph(comment='SkillScopeJob - Comprehensive System Overview')
    dot.attr(rankdir='TB', size='20,14', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='9')
    
    # User and environment
    dot.node('user', '👤 USER\n\n• Uploads CV\n• Sets preferences\n• Views results', 
             fillcolor='#E1F5FE', shape='ellipse')
    dot.node('browser', '🌐 Web Browser\n\nStreamlit Interface\nRunning on localhost:8501', 
             fillcolor='#E8F5E8')
    
    # Main application cluster (actual files)
    with dot.subgraph(name='cluster_main_app') as c:
        c.attr(label='🚀 MAIN APPLICATION (Python)', style='rounded', color='#1976D2')
        
        # Main Streamlit UI
        c.node('streamlit_main', 'streamlit_cv_extraction.py\n\n• Main Streamlit UI & Entry Point\n• User interactions & file uploads\n• Results display & state management', 
               fillcolor='#E3F2FD')
        
        # CV Processing
        c.node('cv_extraction', 'cv_extraction.py\n\n• CV parsing via Together AI LLM\n• Skills & experience extraction\n• Profile data structuring', 
               fillcolor='#E8F5E8')
    
    # Processing engines cluster (actual files)
    with dot.subgraph(name='cluster_processing') as c:
        c.attr(label='⚙️ CORE PROCESSING ENGINES', style='rounded', color='#FF9800')
        
        c.node('indeed_scraper', 'indeed_scraper.py\n\n• Job scraping via JobSpy library\n• Indeed.com data collection\n• Job data cleaning & storage', 
               fillcolor='#FFF3E0')
        
        c.node('job_matcher', 'profile_job_matcher.py\n\n• Profile-to-job matching logic\n• Relevance scoring algorithms\n• SQLAlchemy ORM operations', 
               fillcolor='#FFF3E0')
        
        c.node('cv_evaluator', 'cv_job_evaluator.py\n\n• AI-powered CV vs job analysis\n• Gap analysis & recommendations\n• Together AI LLM integration', 
               fillcolor='#F3E5F5')
        
        c.node('data_enricher', 'data_enrichment_crew.py\n\n• CrewAI framework integration\n• Job data enhancement\n• Company info enrichment', 
               fillcolor='#F3E5F5')
    
    # Data layer cluster (actual files)
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='💾 DATA LAYER', style='rounded', color='#7B1FA2')
        
        c.node('database_models', 'database_models.py\n\n• SQLAlchemy ORM definitions\n• JobPosting, UserProfile models\n• Database engine & session management', 
               fillcolor='#F3E5F5')
        
        c.node('sqlite_db', 'indeed_jobs.db\n\n📊 SQLite Database\n• Job postings storage\n• User profiles & evaluations\n• Application data persistence', 
               fillcolor='#EFEBE9', shape='cylinder')
        
        c.node('ontology_files', 'Ontology & Reference Files\n\n• skill_ontology.csv\n• roles_industries_ontology.csv\n• advanced_user_profile_log.csv', 
               fillcolor='#F3E5F5')
    
    # Configuration cluster (actual files)
    with dot.subgraph(name='cluster_config') as c:
        c.attr(label='⚙️ CONFIGURATION & ADMIN', style='rounded', color='#607D8B')
        
        c.node('requirements', 'requirements.txt\n\n• Python dependencies\n• Package versions\n• Environment setup', 
               fillcolor='#ECEFF1')
        
        c.node('admin_utils', 'admin_utils/\n\n• debug_database.py\n• streamlit_app.py\n• Database management tools', 
               fillcolor='#ECEFF1')
        
        c.node('docs', 'Documentation\n\n• README.md\n• system_architecture.py\n• Project documentation', 
               fillcolor='#ECEFF1')
    
    # External services (actual integrations)
    with dot.subgraph(name='cluster_external') as c:
        c.attr(label='🌐 EXTERNAL SERVICES', style='rounded', color='#D32F2F')
        
        c.node('indeed', 'Indeed.com\n\n• Job listings source\n• Scraped via JobSpy\n• Real-time job data', 
               fillcolor='#FFEBEE', shape='ellipse')
        
        c.node('together_ai', 'Together AI\n\n• Llama 3.x LLM models\n• CV parsing & evaluation\n• Data enrichment', 
               fillcolor='#FFEBEE', shape='ellipse')
    
    # Main user flow
    dot.edge('user', 'browser', label='interacts', color='#1976D2', style='bold')
    dot.edge('browser', 'streamlit_main', label='HTTP requests', color='#1976D2', style='bold')
    dot.edge('streamlit_main', 'cv_extraction', label='CV file', color='#4CAF50', style='bold')
    
    # Processing flow
    dot.edge('cv_extraction', 'together_ai', label='LLM parsing', color='#D32F2F', style='dashed')
    dot.edge('streamlit_main', 'job_matcher', label='search request', color='#FF9800', style='bold')
    dot.edge('job_matcher', 'indeed_scraper', label='trigger scraping', color='#FF9800', style='bold')
    dot.edge('indeed_scraper', 'indeed', label='scrape jobs', color='#D32F2F', style='dashed')
    dot.edge('data_enricher', 'together_ai', label='enhancement LLM', color='#D32F2F', style='dashed')
    dot.edge('cv_evaluator', 'together_ai', label='evaluation LLM', color='#D32F2F', style='dashed')
    
    # Data interactions
    dot.edge('cv_extraction', 'database_models', label='save profile', color='#7B1FA2')
    dot.edge('indeed_scraper', 'database_models', label='store jobs', color='#7B1FA2')
    dot.edge('data_enricher', 'database_models', label='update enrichment', color='#7B1FA2')
    dot.edge('job_matcher', 'database_models', label='query & match', color='#7B1FA2')
    dot.edge('cv_evaluator', 'database_models', label='store evaluations', color='#7B1FA2')
    dot.edge('database_models', 'sqlite_db', label='ORM operations', color='#795548')
    
    # Configuration usage
    dot.edge('streamlit_main', 'ontology_files', label='load references', color='#607D8B', style='dotted')
    dot.edge('admin_utils', 'sqlite_db', label='manage DB', color='#607D8B', style='dashed')
    
    # Results flow
    dot.edge('job_matcher', 'streamlit_main', label='ranked jobs', color='#4CAF50', style='bold')
    dot.edge('cv_evaluator', 'streamlit_main', label='evaluation insights', color='#4CAF50', style='bold')
    
    return dot

def main():
    """Generate the two specific architecture diagrams"""
    
    print("🏗️ Creating Architecture Diagrams...")
    
    # Check Graphviz availability first
    has_graphviz = check_graphviz_installation()
    if not has_graphviz:
        print("\n📝 Continuing with DOT file generation...")
    
    # 1. Component Interaction (matches your first attachment)
    components = create_component_interaction()
    safe_render(components, 'skillscope_component_interaction', 'png')
    
    # 2. Layered Architecture (matches your second attachment)
    layered = create_layered_architecture()
    safe_render(layered, 'skillscope_layered_architecture', 'png')
    
    print("\n📊 Architecture diagrams processed!")
    
    if has_graphviz:
        print("\nDiagrams created:")
        print("  1. skillscope_component_interaction.png")
        print("  2. skillscope_layered_architecture.png")
    else:
        print("\nDOT files created (install Graphviz for PNG generation):")
        print("  1. skillscope_component_interaction.dot")
        print("  2. skillscope_layered_architecture.dot")
        print("\n🌐 View these files online at: https://dreampuf.github.io/GraphvizOnline/")

if __name__ == "__main__":
    main()