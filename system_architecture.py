from graphviz import Digraph

def create_system_architecture():
    # Create a new directed graph
    dot = Digraph(comment='SkillScopeJob System Architecture')
    dot.attr(rankdir='TB')
    
    # Set default node attributes
    dot.attr('node', shape='box', style='rounded')
    
    # Define node colors
    FRONTEND_COLOR = '#ADD8E6'  # Light blue
    CORE_COLOR = '#98FB98'      # Light green
    DB_COLOR = '#FFB6C1'        # Light red
    API_COLOR = '#DDA0DD'       # Light purple
    
    # Create clusters for different system components
    with dot.subgraph(name='cluster_0') as c:
        c.attr(label='Frontend Layer', style='rounded', color='blue')
        c.attr('node', style='filled', fillcolor=FRONTEND_COLOR)
        c.node('streamlit_main', 'Streamlit Main App\n(CV Upload & Analysis)')
        c.node('streamlit_dashboard', 'Streamlit Dashboard\n(Visualization & Analytics)')
        c.edge('streamlit_main', 'streamlit_dashboard')
    
    with dot.subgraph(name='cluster_1') as c:
        c.attr(label='Core Processing Layer', style='rounded', color='green')
        c.attr('node', style='filled', fillcolor=CORE_COLOR)
        c.node('cv_extraction', 'CV Extraction Engine')
        c.node('job_matcher', 'Profile-Job Matcher')
        c.node('cv_evaluator', 'CV-Job Evaluator')
        c.node('skill_analyzer', 'Skill Analyzer')
        
        # Connect core components
        c.edge('cv_extraction', 'job_matcher')
        c.edge('job_matcher', 'cv_evaluator')
        c.edge('cv_extraction', 'skill_analyzer')
        c.edge('skill_analyzer', 'job_matcher')
    
    with dot.subgraph(name='cluster_2') as c:
        c.attr(label='Data Collection Layer', style='rounded', color='red')
        c.attr('node', style='filled', fillcolor=DB_COLOR)
        c.node('job_scraper', 'Job Scraper')
        c.node('data_enrichment', 'Data Enrichment')
        c.edge('job_scraper', 'data_enrichment')
    
    with dot.subgraph(name='cluster_3') as c:
        c.attr(label='External APIs & Services', style='rounded', color='purple')
        c.attr('node', style='filled', fillcolor=API_COLOR)
        c.node('together_ai', 'Together AI API')
        c.node('indeed_api', 'Indeed API')
        c.node('other_apis', 'Other Job APIs')
    
    with dot.subgraph(name='cluster_4') as c:
        c.attr(label='Data Storage Layer', style='rounded', color='orange')
        c.node('sqlite_db', 'SQLite Database')
        c.node('ontologies', 'Ontologies & Taxonomies')
    
    # Connect components across clusters
    dot.edge('streamlit_main', 'cv_extraction')
    dot.edge('cv_extraction', 'together_ai')
    dot.edge('job_scraper', 'indeed_api')
    dot.edge('job_scraper', 'other_apis')
    dot.edge('job_scraper', 'sqlite_db')
    dot.edge('job_matcher', 'sqlite_db')
    dot.edge('data_enrichment', 'together_ai')
    dot.edge('skill_analyzer', 'ontologies')
    dot.edge('cv_evaluator', 'sqlite_db')
    dot.edge('streamlit_dashboard', 'sqlite_db')
    
    # Save the diagram
    dot.render('system_architecture', format='png', cleanup=True)
    print("System architecture diagram has been created: system_architecture.png")

if __name__ == "__main__":
    create_system_architecture() 