from graphviz import Digraph

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
    """Create a clean layered architecture view"""
    
    dot = Digraph(comment='SkillScopeJob - Layered Architecture')
    dot.attr(rankdir='TB', size='12,8', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='11')
    
    # Layer colors
    PRESENTATION_COLOR = '#E3F2FD'
    BUSINESS_COLOR = '#E8F5E8'
    DATA_COLOR = '#FFF3E0'
    EXTERNAL_COLOR = '#F3E5F5'
    
    # Presentation Layer
    with dot.subgraph(name='cluster_presentation') as c:
        c.attr(label='Presentation Layer', style='rounded', color='#1976D2')
        c.attr('node', fillcolor=PRESENTATION_COLOR)
        c.node('web_ui', 'Web Interface\n(Streamlit)\n\n• CV Upload\n• Job Search\n• Results Display')
    
    # Business Logic Layer
    with dot.subgraph(name='cluster_business') as c:
        c.attr(label='Business Logic Layer', style='rounded', color='#388E3C')
        c.attr('node', fillcolor=BUSINESS_COLOR)
        c.node('cv_engine', 'CV Processing\nEngine\n\n• Text Extraction\n• Skill Analysis')
        c.node('matching_engine', 'Job Matching\nEngine\n\n• Profile Matching\n• Relevance Scoring')
        c.node('ai_engine', 'AI Enhancement\nEngine\n\n• Data Enrichment\n• Smart Evaluation')
    
    # Data Layer
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='Data Layer', style='rounded', color='#F57C00')
        c.attr('node', fillcolor=DATA_COLOR)
        c.node('job_collector', 'Job Collection\nService\n\n• Web Scraping\n• Data Cleaning')
        c.node('database', 'Database\n(SQLite)\n\n• Job storage\n• Profile storage')
    
    # External Layer
    with dot.subgraph(name='cluster_external') as c:
        c.attr(label='External Services', style='rounded', color='#7B1FA2')
        c.attr('node', fillcolor=EXTERNAL_COLOR)
        c.node('job_boards', 'Job Boards\n(Indeed)\n\n• Job Listings\n• Company Data')
        c.node('ai_services', 'AI Services\n(Together AI)\n\n• LLM Processing\n• Text Analysis')
    
    # Layer connections
    dot.edge('web_ui', 'cv_engine', label='CV files')
    dot.edge('web_ui', 'matching_engine', label='search requests')
    dot.edge('cv_engine', 'matching_engine', label='user profile')
    dot.edge('matching_engine', 'ai_engine', label='matching data')
    dot.edge('ai_engine', 'database', label='enriched data')
    dot.edge('matching_engine', 'job_collector', label='search criteria')
    dot.edge('job_collector', 'database', label='job data')
    dot.edge('job_collector', 'job_boards', label='scraping', style='dashed')
    dot.edge('ai_engine', 'ai_services', label='API calls', style='dashed')
    dot.edge('database', 'matching_engine', label='stored jobs')
    dot.edge('matching_engine', 'web_ui', label='ranked results')
    
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
    """Create a component interaction focused diagram"""
    
    dot = Digraph(comment='SkillScopeJob - Component Interactions')
    dot.attr(rankdir='TB', size='12,10', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Core components with clear responsibilities
    dot.node('user_interface', 'User Interface\n\n• File Upload\n• Form Input\n• Results Display\n• User Experience', 
             fillcolor='#E3F2FD')
    
    dot.node('cv_processor', 'CV Processor\n\n• PDF Parsing\n• Text Extraction\n• Skill Detection\n• Profile Creation', 
             fillcolor='#E8F5E8')
    
    dot.node('job_scraper', 'Job Scraper\n\n• Web Scraping\n• Data Collection\n• Deduplication\n• Storage', 
             fillcolor='#FFF3E0')
    
    dot.node('ai_enricher', 'AI Enricher\n\n• Company Research\n• Industry Classification\n• Data Enhancement\n• Quality Improvement', 
             fillcolor='#F3E5F5')
    
    dot.node('job_matcher', 'Job Matcher\n\n• Profile Matching\n• Relevance Scoring\n• Result Ranking\n• Personalization', 
             fillcolor='#E8F5E8')
    
    dot.node('data_store', 'Data Store\n\n• Job Database\n• User Profiles\n• Search History\n• System State', 
             fillcolor='#FFEBEE')
    
    # Interaction flows with clear labels
    dot.edge('user_interface', 'cv_processor', label='CV upload\n& processing', color='#1976D2')
    dot.edge('cv_processor', 'job_scraper', label='search criteria\n& preferences', color='#388E3C')
    dot.edge('job_scraper', 'data_store', label='raw job data\n& metadata', color='#F57C00')
    dot.edge('data_store', 'ai_enricher', label='incomplete\njob records', color='#7B1FA2')
    dot.edge('ai_enricher', 'data_store', label='enriched\ncompany data', color='#7B1FA2')
    dot.edge('data_store', 'job_matcher', label='enriched jobs\n& user profile', color='#D32F2F')
    dot.edge('job_matcher', 'user_interface', label='ranked results\n& insights', color='#1976D2')
    
    # Bidirectional relationships
    dot.edge('cv_processor', 'data_store', label='user profile\nstorage', color='#388E3C', style='dashed')
    dot.edge('job_matcher', 'data_store', label='query jobs\n& analytics', color='#D32F2F', style='dashed')
    
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
    """Create architecture diagram showing actual files and their relationships"""
    
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
    
    # UI Layer
    with dot.subgraph(name='cluster_ui') as c:
        c.attr(label='🎨 User Interface & Entry', style='rounded', color=UI_COLOR, fontcolor=UI_COLOR)
        c.node('streamlit_cv_extraction_py', 'streamlit_cv_extraction.py\n\n• Main Streamlit App UI\n• User Profile Input\n• CV Upload & Basic Parsing Trigger\n• Job Search Trigger\n• Results Display\n• CV Evaluation Trigger', 
               fillcolor=UI_COLOR + '30', color=UI_COLOR)

    # CV Processing & Extraction Layer
    with dot.subgraph(name='cluster_cv_proc') as c:
        c.attr(label='📄 CV Processing & Extraction', style='rounded', color=CV_PROCESSING_COLOR, fontcolor=CV_PROCESSING_COLOR)
        c.node('cv_extraction_py', 'cv_extraction.py\n\n• LLM-based CV Parsing\n• Extracts (Skills, Experience, Edu)\n• Suggests Profile Fields',
               fillcolor=CV_PROCESSING_COLOR + '30', color=CV_PROCESSING_COLOR)

    # Core Job Matching, Scraping & Evaluation Layer
    with dot.subgraph(name='cluster_job_core') as c:
        c.attr(label='⚙️ Job Scraping, Matching & Evaluation', style='rounded', color=JOB_PROCESSING_COLOR, fontcolor=JOB_PROCESSING_COLOR)
        c.node('indeed_scraper_py', 'indeed_scraper.py\n\n• Scrapes Indeed.com\n• Stores raw job postings (initially SQLite, now ORM)\n• Handles job URL uniqueness', 
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)
        c.node('profile_job_matcher_py', 'profile_job_matcher.py\n\n• Matches User Profile to Jobs (DB & Live)\n• Uses SQLAlchemy for DB interaction\n• Calculates Relevance Scores\n• Updates user_profile_match in DB',
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)
        c.node('cv_job_evaluator_py', 'cv_job_evaluator.py\n\n• LLM-based CV vs. Job Description Analysis\n• Detailed Match Feedback (Strengths, Gaps)\n• Stores evaluation results (partially SQLAlchemy now)',
               fillcolor=JOB_PROCESSING_COLOR + '30', color=JOB_PROCESSING_COLOR)

    # Data Enrichment (CrewAI) Layer
    with dot.subgraph(name='cluster_enrich') as c:
        c.attr(label='🤖 AI Data Enrichment', style='rounded', color=AI_COLOR, fontcolor=AI_COLOR)
        c.node('data_enrichment_crew_py', 'data_enrichment_crew.py\n\n• Uses CrewAI for Job Data Enrichment\n• Company Info, Industry, Logo, etc.\n• Updates job_postings table (enrichment_status, job_freshness)',
               fillcolor=AI_COLOR + '30', color=AI_COLOR)

    # Data Models & Database Layer
    with dot.subgraph(name='cluster_data_models_db') as c:
        c.attr(label='💾 Data Models & Database', style='rounded', color=DATA_MGMT_COLOR, fontcolor=DATA_MGMT_COLOR)
        c.node('database_models_py', 'database_models.py\n\n• SQLAlchemy ORM Models (JobPosting, UserProfile, etc.)\n• Table Schemas & Relationships\n• Database Engine & SessionLocal Setup',
               fillcolor=DATA_MGMT_COLOR + '30', color=DATA_MGMT_COLOR)
        c.node('indeed_jobs_db', 'indeed_jobs.db\n\n• SQLite Database File\n• Stores all application data', 
               fillcolor=DATABASE_FILE_COLOR + '30', color=DATABASE_FILE_COLOR, shape='cylinder')

    # Configuration & Ontology Files
    with dot.subgraph(name='cluster_config_ontology') as c:
        c.attr(label='⚙️ Configuration & Ontologies', style='rounded', color=CONFIG_COLOR, fontcolor=CONFIG_COLOR)
        c.node('requirements_txt', 'requirements.txt\n\n• Python Dependencies', 
               fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('env_file', '.env (example)\n\n• API Keys (TogetherAI)\n• Environment Variables',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('skill_ontology_csv', 'skill_ontology.csv\n\n• Predefined Skills List',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)
        c.node('roles_industries_ontology_csv', 'roles_industries_ontology.csv\n\n• Predefined Roles/Industries',
                fillcolor=CONFIG_COLOR + '30', color=CONFIG_COLOR)

    # External Services (Conceptual)
    with dot.subgraph(name='cluster_external_conceptual') as c:
        c.attr(label='🌐 External Services (Conceptual)', style='rounded', color='#D32F2F', fontcolor='#D32F2F')
        c.node('indeed_service', 'Indeed.com\n\n• Source for Job Listings', 
               fillcolor='#FFEBEE', color='#D32F2F', shape='ellipse')
        c.node('together_ai_service', 'Together AI API\n\n• LLM for CV Parsing & Evaluation', 
               fillcolor='#FFEBEE', color='#D32F2F', shape='ellipse')

    # --- Relationships ---

    # UI to Processing
    dot.edge('streamlit_cv_extraction_py', 'cv_extraction_py', label='triggers CV parsing', color=CV_PROCESSING_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'profile_job_matcher_py', label='triggers job search / profile storage', color=JOB_PROCESSING_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'cv_job_evaluator_py', label='triggers CV evaluation', color=JOB_PROCESSING_COLOR)

    # CV Processing to Models & AI
    dot.edge('cv_extraction_py', 'together_ai_service', label='uses LLM for CV', style='dashed', color=AI_COLOR)
    dot.edge('cv_extraction_py', 'database_models_py', label='informs profile structure (conceptually)', style='dotted', color=DATA_MGMT_COLOR) # CV suggestions map to UserProfile

    # Job Core to Data & External
    dot.edge('indeed_scraper_py', 'indeed_service', label='scrapes from', style='dashed', color=JOB_PROCESSING_COLOR)
    dot.edge('indeed_scraper_py', 'database_models_py', label='uses JobPosting model', color=DATA_MGMT_COLOR)
    
    dot.edge('profile_job_matcher_py', 'database_models_py', label='uses UserProfile, JobPosting models', color=DATA_MGMT_COLOR)
    dot.edge('profile_job_matcher_py', 'indeed_scraper_py', label='can trigger live scraping', color=JOB_PROCESSING_COLOR) # For live results

    dot.edge('cv_job_evaluator_py', 'database_models_py', label='uses UserProfile, CVJobEvaluation models', color=DATA_MGMT_COLOR)
    dot.edge('cv_job_evaluator_py', 'together_ai_service', label='uses LLM for evaluation', style='dashed', color=AI_COLOR)

    # Data Enrichment to Data & External
    dot.edge('data_enrichment_crew_py', 'database_models_py', label='updates JobPosting model', color=DATA_MGMT_COLOR)
    # data_enrichment_crew_py also uses LLMs, potentially via TogetherAI or other services for company info.
    dot.edge('data_enrichment_crew_py', 'together_ai_service', label='uses LLM for enrichment (conceptual)', style='dashed', color=AI_COLOR)


    # Database Interactions (explicitly via database_models.py)
    dot.edge('database_models_py', 'indeed_jobs_db', label='defines & connects to', color=DATABASE_FILE_COLOR)
    
    # UI reads ontologies
    dot.edge('streamlit_cv_extraction_py', 'skill_ontology_csv', label='reads skills', style='dotted', color=CONFIG_COLOR)
    dot.edge('streamlit_cv_extraction_py', 'roles_industries_ontology_csv', label='reads roles', style='dotted', color=CONFIG_COLOR)

    # Config usage
    dot.edge('env_file', 'cv_extraction_py', label='API Key', style='dashed', color=CONFIG_COLOR)
    dot.edge('env_file', 'cv_job_evaluator_py', label='API Key', style='dashed', color=CONFIG_COLOR)
    dot.edge('env_file', 'data_enrichment_crew_py', label='API Key (conceptual)', style='dashed', color=CONFIG_COLOR)
    
    return dot

def create_module_dependency_diagram():
    """Create a module dependency diagram showing imports and relationships"""
    
    dot = Digraph(comment='SkillScopeJob - Module Dependencies')
    dot.attr(rankdir='LR', size='18,10', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Python modules with their dependencies
    modules = {
        'main.py': {
            'imports': ['streamlit', 'app'],
            'color': '#1976D2',
            'description': 'Entry Point\n\n• App launcher\n• Configuration'
        },
        'app.py': {
            'imports': ['streamlit', 'cv_processor', 'job_matcher', 'ui_components', 'database'],
            'color': '#4CAF50',
            'description': 'Main App\n\n• UI logic\n• User flow\n• State management'
        },
        'cv_processor.py': {
            'imports': ['pandas', 'PyPDF2', 'docx', 'data_models'],
            'color': '#FF9800',
            'description': 'CV Processing\n\n• PDF parsing\n• Text extraction\n• Skill analysis'
        },
        'job_scraper.py': {
            'imports': ['jobspy', 'pandas', 'requests', 'database', 'config'],
            'color': '#FF9800',
            'description': 'Job Scraping\n\n• Web scraping\n• Data collection\n• API integration'
        },
        'job_matcher.py': {
            'imports': ['pandas', 'numpy', 'database', 'ai_enrichment', 'data_models'],
            'color': '#FF9800',
            'description': 'Job Matching\n\n• Relevance scoring\n• Profile matching\n• Result ranking'
        },
        'ai_enrichment.py': {
            'imports': ['openai', 'requests', 'pandas', 'config', 'database'],
            'color': '#9C27B0',
            'description': 'AI Enhancement\n\n• LLM processing\n• Data enrichment\n• Smart analysis'
        },
        'database.py': {
            'imports': ['sqlite3', 'pandas', 'datetime', 'data_models'],
            'color': '#795548',
            'description': 'Database Layer\n\n• SQLite operations\n• Data persistence\n• Query management'
        },
        'ui_components.py': {
            'imports': ['streamlit', 'plotly', 'pandas'],
            'color': '#4CAF50',
            'description': 'UI Components\n\n• Custom widgets\n• Charts & graphs\n• Interactive elements'
        },
        'data_models.py': {
            'imports': ['dataclasses', 'typing', 'datetime'],
            'color': '#607D8B',
            'description': 'Data Models\n\n• Type definitions\n• Data structures\n• Validation'
        },
        'config.py': {
            'imports': ['os', 'dotenv'],
            'color': '#607D8B',
            'description': 'Configuration\n\n• Settings\n• Environment vars\n• Constants'
        }
    }
    
    # Add module nodes
    for module, info in modules.items():
        dot.node(module.replace('.py', ''), f"{module}\n\n{info['description']}", 
                fillcolor=f"{info['color']}30", color=info['color'])
    
    # Add dependency edges
    for module, info in modules.items():
        module_name = module.replace('.py', '')
        for imported in info['imports']:
            if imported in [m.replace('.py', '') for m in modules.keys()]:
                dot.edge(module_name, imported, label='imports', color=info['color'], style='dashed')
    
    # Add external library dependencies
    external_libs = {
        'streamlit': '#FF4B4B',
        'pandas': '#150458',
        'jobspy': '#FFA500',
        'sqlite3': '#003B57',
        'openai': '#412991',
        'plotly': '#3F4F75'
    }
    
    for lib, color in external_libs.items():
        dot.node(lib, f"{lib}\n(External Library)", fillcolor=f"{color}20", color=color, shape='ellipse')
    
    # Connect modules to external libraries
    for module, info in modules.items():
        module_name = module.replace('.py', '')
        for imported in info['imports']:
            if imported in external_libs:
                dot.edge(module_name, imported, label='uses', color=external_libs[imported], style='dotted')
    
    return dot

def create_application_flow_with_files():
    """Create application flow showing file execution order and data flow"""
    
    dot = Digraph(comment='SkillScopeJob - Application Flow with Files')
    dot.attr(rankdir='TB', size='14,16', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='10')
    
    # Execution phases with files
    phases = [
        {
            'name': 'initialization',
            'label': '🚀 INITIALIZATION PHASE',
            'files': [
                ('main_py', 'main.py\nLaunches Streamlit app', '#E3F2FD'),
                ('config_load', 'config.py\nLoads environment settings', '#ECEFF1'),
                ('database_init', 'database.py\nInitializes SQLite connection', '#F3E5F5')
            ]
        },
        {
            'name': 'user_interaction',
            'label': '👤 USER INTERACTION PHASE',
            'files': [
                ('app_start', 'app.py\nRenders main interface', '#E8F5E8'),
                ('ui_components', 'ui_components.py\nDisplays upload forms', '#E8F5E8'),
                ('file_upload', 'User uploads CV file\n(PDF/DOCX)', '#FFF9C4')
            ]
        },
        {
            'name': 'cv_processing',
            'label': '📄 CV PROCESSING PHASE',
            'files': [
                ('cv_parse', 'cv_processor.py\nParses uploaded CV', '#FFF3E0'),
                ('skill_extract', 'Extract skills & experience\nCreate user profile', '#FFF3E0'),
                ('profile_save', 'database.py\nSaves user profile', '#F3E5F5')
            ]
        },
        {
            'name': 'job_search',
            'label': '🔍 JOB SEARCH PHASE',
            'files': [
                ('job_scrape', 'job_scraper.py\nScrapes job sites', '#FFEBEE'),
                ('indeed_api', 'Indeed API\nFetches job listings', '#FFCDD2'),
                ('job_store', 'database.py\nStores raw job data', '#F3E5F5')
            ]
        },
        {
            'name': 'ai_enhancement',
            'label': '🤖 AI ENHANCEMENT PHASE',
            'files': [
                ('ai_process', 'ai_enrichment.py\nEnhances job data', '#F3E5F5'),
                ('together_ai', 'Together AI API\nLLM processing', '#E1F5FE'),
                ('data_update', 'database.py\nUpdates enriched data', '#F3E5F5')
            ]
        },
        {
            'name': 'matching',
            'label': '🎯 MATCHING PHASE',
            'files': [
                ('job_match', 'job_matcher.py\nMatches jobs to profile', '#E8F5E8'),
                ('relevance_score', 'Calculate relevance scores\nRank results', '#E8F5E8'),
                ('final_results', 'app.py\nDisplays ranked results', '#E8F5E8')
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
    """Create a visual representation of the project repository structure"""
    
    dot = Digraph(comment='SkillScopeJob - Repository Structure')
    dot.attr(rankdir='TB', size='12,14', dpi='200')
    dot.attr('node', shape='folder', style='filled', fontsize='10')
    
    # Root folder
    dot.node('root', 'SkillScopeJob-1/\n📁 Root Directory', fillcolor='#FFF3E0')
    
    # Main application files
    dot.node('app_files', '📄 Application Files\n\n• main.py\n• app.py\n• cv_processor.py\n• job_scraper.py\n• job_matcher.py\n• ai_enrichment.py', 
             fillcolor='#E3F2FD', shape='box')
    
    # Data and database files
    dot.node('data_files', '💾 Data Files\n\n• database.py\n• data_models.py\n• jobs.db (SQLite)', 
             fillcolor='#F3E5F5', shape='box')
    
    # Configuration files
    dot.node('config_files', '⚙️ Configuration\n\n• config.py\n• .env\n• requirements.txt', 
             fillcolor='#ECEFF1', shape='box')
    
    # UI and assets
    dot.node('ui_files', '🎨 UI & Assets\n\n• ui_components.py\n• styles.css\n• images/\n• templates/', 
             fillcolor='#E8F5E8', shape='box')
    
    # Documentation
    dot.node('docs', '📚 Documentation\n\n• README.md\n• system_architecture.py\n• docs/', 
             fillcolor='#FFF8E1', shape='box')
    
    # Tests (if they exist)
    dot.node('tests', '🧪 Tests\n\n• test_cv_processor.py\n• test_job_matcher.py\n• tests/', 
             fillcolor='#FFEBEE', shape='box')
    
    # Logs and temp files
    dot.node('temp_files', '📝 Runtime Files\n\n• logs/\n• temp/\n• uploads/\n• cache/', 
             fillcolor='#F5F5F5', shape='box')
    
    # Connect to root
    for node in ['app_files', 'data_files', 'config_files', 'ui_files', 'docs', 'tests', 'temp_files']:
        dot.edge('root', node)
    
    # Show relationships between file groups
    dot.edge('app_files', 'data_files', label='uses', style='dashed')
    dot.edge('app_files', 'config_files', label='imports', style='dashed')
    dot.edge('app_files', 'ui_files', label='renders', style='dashed')
    dot.edge('tests', 'app_files', label='tests', style='dotted')
    
    return dot

def create_comprehensive_system_overview():
    """Create the most comprehensive system overview with everything"""
    
    dot = Digraph(comment='SkillScopeJob - Comprehensive System Overview')
    dot.attr(rankdir='TB', size='20,14', dpi='200')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='9')
    
    # User and environment
    dot.node('user', '👤 USER\n\n• Uploads CV\n• Sets preferences\n• Views results', 
             fillcolor='#E1F5FE', shape='ellipse')
    dot.node('browser', '🌐 Web Browser\n\nStreamlit Interface\nRunning on localhost:8501', 
             fillcolor='#E8F5E8')
    
    # Main application cluster
    with dot.subgraph(name='cluster_main_app') as c:
        c.attr(label='🚀 MAIN APPLICATION (Python)', style='rounded', color='#1976D2')
        
        # Entry point
        c.node('main_py', 'main.py\n\n• Entry point\n• Streamlit runner\n• App configuration', 
               fillcolor='#E3F2FD')
        
        # Core application
        c.node('app_py', 'app.py\n\n• Main UI logic\n• User interactions\n• State management\n• Result display', 
               fillcolor='#E3F2FD')
        
        # UI components
        c.node('ui_comp', 'ui_components.py\n\n• Custom widgets\n• Forms & inputs\n• Charts & visualizations', 
               fillcolor='#E8F5E8')
    
    # Processing engines cluster
    with dot.subgraph(name='cluster_processing') as c:
        c.attr(label='⚙️ PROCESSING ENGINES', style='rounded', color='#FF9800')
        
        c.node('cv_proc', 'cv_processor.py\n\n• PDF/DOCX parsing\n• Text extraction\n• Skill detection\n• Profile creation', 
               fillcolor='#FFF3E0')
        
        c.node('job_scraper', 'job_scraper.py\n\n• Web scraping\n• Job data collection\n• Indeed integration\n• Data cleaning', 
               fillcolor='#FFF3E0')
        
        c.node('job_matcher', 'job_matcher.py\n\n• Profile matching\n• Relevance scoring\n• Result ranking\n• Personalization', 
               fillcolor='#FFF3E0')
        
        c.node('ai_enrich', 'ai_enrichment.py\n\n• LLM integration\n• Data enhancement\n• Smart analysis\n• Company research', 
               fillcolor='#F3E5F5')
    
    # Data layer cluster
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='💾 DATA LAYER', style='rounded', color='#7B1FA2')
        
        c.node('database_py', 'database.py\n\n• SQLite operations\n• CRUD functions\n• Query management\n• Schema handling', 
               fillcolor='#F3E5F5')
        
        c.node('data_models', 'data_models.py\n\n• Data structures\n• Type definitions\n• Validation logic', 
               fillcolor='#F3E5F5')
        
        c.node('sqlite_db', 'jobs.db\n\n📊 SQLite Database\n• Job postings\n• User profiles\n• Search history', 
               fillcolor='#EFEBE9', shape='cylinder')
    
    # Configuration cluster
    with dot.subgraph(name='cluster_config') as c:
        c.attr(label='⚙️ CONFIGURATION', style='rounded', color='#607D8B')
        
        c.node('config_py', 'config.py\n\n• App settings\n• API configuration\n• Constants', 
               fillcolor='#ECEFF1')
        
        c.node('env_vars', '.env\n\n• Environment variables\n• Secret keys\n• Local settings', 
               fillcolor='#ECEFF1')
        
        c.node('requirements', 'requirements.txt\n\n• Python dependencies\n• Package versions', 
               fillcolor='#ECEFF1')
    
    # External services
    with dot.subgraph(name='cluster_external') as c:
        c.attr(label='🌐 EXTERNAL SERVICES', style='rounded', color='#D32F2F')
        
        c.node('indeed', 'Indeed API\n\n• Job listings\n• Company data\n• Search results', 
               fillcolor='#FFEBEE', shape='ellipse')
        
        c.node('together_ai', 'Together AI\n\n• Llama 3.3 70B\n• Text processing\n• AI analysis', 
               fillcolor='#FFEBEE', shape='ellipse')
    
    # Main user flow
    dot.edge('user', 'browser', label='interacts', color='#1976D2', style='bold')
    dot.edge('browser', 'main_py', label='HTTP requests', color='#1976D2', style='bold')
    dot.edge('main_py', 'app_py', label='launches', color='#1976D2', style='bold')
    dot.edge('app_py', 'ui_comp', label='renders UI', color='#4CAF50')
    
    # Processing flow
    dot.edge('app_py', 'cv_proc', label='CV file', color='#FF9800', style='bold')
    dot.edge('cv_proc', 'job_scraper', label='search criteria', color='#FF9800', style='bold')
    dot.edge('job_scraper', 'ai_enrich', label='raw job data', color='#FF9800', style='bold')
    dot.edge('ai_enrich', 'job_matcher', label='enriched data', color='#FF9800', style='bold')
    dot.edge('job_matcher', 'app_py', label='ranked results', color='#4CAF50', style='bold')
    
    # Data interactions
    dot.edge('cv_proc', 'database_py', label='save profile', color='#7B1FA2')
    dot.edge('job_scraper', 'database_py', label='store jobs', color='#7B1FA2')
    dot.edge('ai_enrich', 'database_py', label='update data', color='#7B1FA2')
    dot.edge('job_matcher', 'database_py', label='query jobs', color='#7B1FA2')
    dot.edge('database_py', 'sqlite_db', label='SQL operations', color='#795548')
    
    # Configuration usage
    dot.edge('config_py', 'job_scraper', label='settings', color='#607D8B', style='dashed')
    dot.edge('config_py', 'ai_enrich', label='API keys', color='#607D8B', style='dashed')
    dot.edge('env_vars', 'config_py', label='env vars', color='#607D8B', style='dashed')
    
    # External API calls
    dot.edge('job_scraper', 'indeed', label='scrapes jobs', color='#D32F2F', style='dashed')
    dot.edge('ai_enrich', 'together_ai', label='LLM requests', color='#D32F2F', style='dashed')
    
    # Data model usage
    dot.edge('data_models', 'cv_proc', label='models', color='#9C27B0', style='dotted')
    dot.edge('data_models', 'job_scraper', label='models', color='#9C27B0', style='dotted')
    dot.edge('data_models', 'database_py', label='schema', color='#9C27B0', style='dotted')
    
    return dot

def main():
    """Generate the two specific architecture diagrams"""
    
    print("🏗️ Creating Architecture Diagrams...")
    
    # 1. Component Interaction (matches your first attachment)
    components = create_component_interaction()
    components.render('skillscope_component_interaction', format='png', cleanup=True)
    print("✅ Component interaction: skillscope_component_interaction.png")
    
    # 2. Layered Architecture (matches your second attachment)
    layered = create_layered_architecture()
    layered.render('skillscope_layered_architecture', format='png', cleanup=True)
    print("✅ Layered architecture: skillscope_layered_architecture.png")
    
    print("\n📊 Architecture diagrams generated!")
    print("\nDiagrams created:")
    print("  1. skillscope_component_interaction.png (Component interactions & data flow)")
    print("  2. skillscope_layered_architecture.png (Clean layer separation)")

if __name__ == "__main__":
    main()