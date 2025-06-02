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
    AI_COLOR = '#FFE0B2'          # Light amber - for AI evaluation
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
        c.node('results_display', 'Enhanced Results Display\n• Job matching scores\n• AI evaluation insights\n• Recommendations')
    
    # Core Engine
    with dot.subgraph(name='cluster_engine') as c:
        c.attr(label='Core Matching Engine', style='rounded', color='#F57C00')
        c.attr('node', fillcolor=ENGINE_COLOR)
        
        c.node('job_matcher', 'Job Matcher\n• Search jobs\n• Initial filtering\n• Candidate selection')
        c.node('job_scraper', 'Job Scraper\n• Collect job data\n• Remove duplicates\n• Store in database')
    
    # Data & AI Layer
    with dot.subgraph(name='cluster_data') as c:
        c.attr(label='Data & Intelligence', style='rounded', color='#7B1FA2')
        c.attr('node', fillcolor=DATA_COLOR)
        
        c.node('database', 'SQLite Database\n• Job postings\n• User profiles\n• Auto-cleanup')
        c.node('ai_enrichment', 'AI Enrichment\n• Company info\n• Industry classification\n• Data enhancement')
    
    # AI Evaluation Layer - NEW
    with dot.subgraph(name='cluster_ai_eval') as c:
        c.attr(label='AI Evaluation & Intelligence', style='rounded', color='#FF8F00')
        c.attr('node', fillcolor=AI_COLOR)
        
        c.node('ai_evaluator', 'LLM Job Evaluator\n• CV-Job compatibility\n• Skill gap analysis\n• Match scoring\n• Recommendations')
        c.node('intelligent_ranking', 'Intelligent Ranking\n• Personalized scoring\n• Context-aware ranking\n• Success prediction')
    
    # External Services
    with dot.subgraph(name='cluster_external') as c:
        c.attr(label='External Services', style='rounded', color='#455A64')
        c.attr('node', fillcolor=EXTERNAL_COLOR)
        
        c.node('indeed', 'Indeed API\n• Job listings\n• Company data', shape='ellipse')
        c.node('together_ai', 'Together AI\n• LLM processing\n• Text analysis\n• Evaluation logic', shape='ellipse')
    
    # Enhanced data flow with AI evaluation
    
    # Initial user interaction
    dot.edge('user', 'streamlit_ui', label='interacts', color='#1976D2')
    dot.edge('streamlit_ui', 'cv_processor', label='CV file', color='#2E7D32')
    dot.edge('cv_processor', 'job_matcher', label='user profile', color='#2E7D32')
    
    # Job collection and storage
    dot.edge('job_matcher', 'job_scraper', label='search request', color='#F57C00')
    dot.edge('job_scraper', 'indeed', label='scrape', color='#F57C00', style='dashed')
    dot.edge('job_scraper', 'database', label='store raw jobs', color='#F57C00')
    
    # Data enrichment
    dot.edge('database', 'ai_enrichment', label='raw data', color='#7B1FA2')
    dot.edge('ai_enrichment', 'together_ai', label='enrichment API', color='#7B1FA2', style='dashed')
    dot.edge('ai_enrichment', 'database', label='enriched data', color='#7B1FA2')
    
    # NEW: AI Evaluation Pipeline
    dot.edge('database', 'ai_evaluator', label='enriched jobs + profile', color='#FF8F00')
    dot.edge('ai_evaluator', 'together_ai', label='evaluation API', color='#FF8F00', style='dashed')
    dot.edge('ai_evaluator', 'intelligent_ranking', label='evaluation results', color='#FF8F00')
    
    # Results flow back to user
    dot.edge('intelligent_ranking', 'results_display', label='ranked matches\n+ insights', color='#FF8F00')
    dot.edge('results_display', 'user', label='displays intelligent\nmatches', color='#1976D2')
    
    # Secondary flows
    dot.edge('job_matcher', 'database', label='query existing', color='#F57C00', style='dotted')
    dot.edge('cv_processor', 'ai_evaluator', label='user skills profile', color='#2E7D32', style='dotted')
    
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

def create_simplified_architecture():
    """Create a simplified, clean system architecture diagram"""
    
    dot = Digraph(comment='SkillScopeJob - Simplified Architecture')
    dot.attr(rankdir='TB', size='12,8', dpi='200')
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

def create_simple_data_flow():
    """Create a simple linear data flow diagram"""
    
    dot = Digraph(comment='SkillScopeJob - Data Flow')
    dot.attr(rankdir='LR', size='14,6')
    dot.attr('node', shape='ellipse', style='filled', fontsize='10')
    
    # Sequential flow
    steps = [
        ('upload', 'CV Upload', '#E3F2FD'),
        ('extract', 'Extract Skills', '#E8F5E8'),
        ('search', 'Search Jobs', '#FFF3E0'),
        ('enrich', 'AI Enhance', '#F3E5F5'),
        ('match', 'Match & Score', '#FFF3E0'),
        ('display', 'Show Results', '#E3F2FD')
    ]
    
    # Add nodes
    for i, (node_id, label, color) in enumerate(steps):
        dot.node(node_id, f"{i+1}. {label}", fillcolor=color)
    
    # Connect sequentially
    for i in range(len(steps)-1):
        current = steps[i][0]
        next_step = steps[i+1][0]
        dot.edge(current, next_step)
    
    return dot

def create_component_overview():
    """Create a high-level component overview"""
    
    dot = Digraph(comment='SkillScopeJob - Components')
    dot.attr(rankdir='TB', size='10,8')
    dot.attr('node', shape='box', style='rounded,filled', fontsize='11')
    
    # Main components
    dot.node('frontend', 'Frontend\n(Streamlit UI)', fillcolor='#E3F2FD')
    dot.node('backend', 'Backend\n(Python Core)', fillcolor='#E8F5E8')
    dot.node('database', 'Database\n(SQLite)', fillcolor='#FFEBEE')
    dot.node('ai', 'AI Services\n(Together AI)', fillcolor='#F3E5F5')
    dot.node('scraper', 'Web Scraper\n(Indeed)', fillcolor='#FFF3E0')
    
    # Connections
    dot.edge('frontend', 'backend', label='user requests')
    dot.edge('backend', 'database', label='data storage')
    dot.edge('backend', 'ai', label='enrichment')
    dot.edge('backend', 'scraper', label='job collection')
    dot.edge('scraper', 'database', label='job data')
    dot.edge('database', 'frontend', label='results')
    
    return dot

def main():
    """Generate enhanced architecture diagrams with AI evaluation"""
    
    print("🏗️ Generating Enhanced SkillScopeJob Architecture with AI Evaluation...")
    
    # Main simplified architecture with AI evaluation
    arch = create_simplified_architecture()
    arch.render('skillscopejob_ai_architecture', format='png', cleanup=True)
    print("✅ Enhanced architecture: skillscopejob_ai_architecture.png")
    
    # Enhanced data flow
    flow = create_enhanced_data_flow()
    flow.render('skillscopejob_ai_flow', format='png', cleanup=True)
    print("✅ Enhanced data flow: skillscopejob_ai_flow.png")
    
    # AI evaluation detail
    ai_detail = create_ai_evaluation_detail()
    ai_detail.render('skillscopejob_ai_evaluation_detail', format='png', cleanup=True)
    print("✅ AI evaluation detail: skillscopejob_ai_evaluation_detail.png")
    
    # Component overview
    components = create_component_overview()
    components.render('skillscopejob_components', format='png', cleanup=True)
    print("✅ Component overview: skillscopejob_components.png")
    
    print("\n📊 Enhanced diagrams with AI evaluation generated!")
    print("Files created:")
    print("  - skillscopejob_ai_architecture.png (Architecture with AI evaluation)")
    print("  - skillscopejob_ai_flow.png (Enhanced 7-step process)")
    print("  - skillscopejob_ai_evaluation_detail.png (AI evaluation internals)")
    print("  - skillscopejob_components.png (High-level components)")

if __name__ == "__main__":
    main()