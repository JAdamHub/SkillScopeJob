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
        c.node('database', 'Database\n(SQLite)\n\n• Job Storage\n• Profile Storage')
    
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

def main():
    """Generate multiple alternative architecture diagrams"""
    
    print("🏗️ Creating Multiple Architecture Views...")
    
    # 1. Layered Architecture
    layered = create_layered_architecture()
    layered.render('skillscope_layered_architecture', format='png', cleanup=True)
    print("✅ Layered architecture: skillscope_layered_architecture.png")
    
    # 2. User Journey Flow
    journey = create_user_journey_flow()
    journey.render('skillscope_user_journey', format='png', cleanup=True)
    print("✅ User journey flow: skillscope_user_journey.png")
    
    # 3. Technology Stack
    tech_stack = create_technology_stack()
    tech_stack.render('skillscope_technology_stack', format='png', cleanup=True)
    print("✅ Technology stack: skillscope_technology_stack.png")
    
    # 4. Data Transformation Flow
    data_flow = create_data_transformation_flow()
    data_flow.render('skillscope_data_transformation', format='png', cleanup=True)
    print("✅ Data transformation: skillscope_data_transformation.png")
    
    # 5. Component Interaction
    components = create_component_interaction()
    components.render('skillscope_component_interaction', format='png', cleanup=True)
    print("✅ Component interaction: skillscope_component_interaction.png")
    
    # 6. Simple Overview
    simple = create_simple_overview()
    simple.render('skillscope_simple_overview', format='png', cleanup=True)
    print("✅ Simple overview: skillscope_simple_overview.png")
    
    # Original enhanced architecture
    arch = create_simplified_architecture()
    arch.render('skillscopejob_ai_architecture', format='png', cleanup=True)
    print("✅ Enhanced architecture: skillscopejob_ai_architecture.png")
    
    print("\n📊 All architecture diagrams generated!")
    print("\nDiagrams created:")
    print("  1. skillscope_layered_architecture.png (Clean layer separation)")
    print("  2. skillscope_user_journey.png (User-centric flow)")
    print("  3. skillscope_technology_stack.png (Technical components)")
    print("  4. skillscope_data_transformation.png (Data processing pipeline)")
    print("  5. skillscope_component_interaction.png (Component relationships)")
    print("  6. skillscope_simple_overview.png (Simplest explanation)")
    print("  7. skillscopejob_ai_architecture.png (Detailed AI architecture)")

if __name__ == "__main__":
    main()