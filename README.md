# 🎯 SkillScopeJob - AI-Powered Career Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io)
[![Together AI](https://img.shields.io/badge/Together%20AI-LLM-green.svg)](https://together.ai)
[![SQLite](https://img.shields.io/badge/SQLite-Database-lightblue.svg)](https://sqlite.org)

**SkillScopeJob** is an advanced AI-powered career intelligence platform that combines CV analysis, job market intelligence, and personalized career recommendations to help professionals make data-driven career decisions.

## 🌟 Features

### 🤖 AI-Powered CV Analysis
- **Intelligent CV Parsing**: Extract skills, experience, and qualifications from PDF, DOCX, and TXT files
- **Auto-Fill Profile Forms**: Automatically populate user profiles from CV data
- **Multi-Model Support**: Choose from various LLM models (Llama 3.2, Llama 3.1, Mixtral)
- **Contact Information Extraction**: Parse names, emails, phone numbers, and LinkedIn profiles

### 🔍 Real-Time Job Market Intelligence
- **Live Job Scraping**: Real-time job data from Indeed using python-jobspy
- **Intelligent Job Matching**: AI-powered relevance scoring and job-profile matching
- **Multi-Source Search**: Live scraping with database fallback for reliability
- **Location-Aware Search**: Support for all Danish municipalities and remote work preferences

### 📊 Advanced Analytics & Evaluation
- **CV-Job Compatibility Analysis**: Deep AI analysis of CV fit against specific job requirements
- **Match Scoring**: Comprehensive scoring system with strengths, gaps, and recommendations
- **Career Improvement Plans**: Personalized AI-generated development recommendations
- **Data Enrichment**: Company and industry information enhancement via CrewAI

### 🎨 Modern User Experience
- **Interactive Streamlit Interface**: Beautiful, responsive web application
- **Real-Time Progress Tracking**: Live updates during job searches and analysis
- **Export Capabilities**: Download results in multiple formats (Markdown, Text, CSV)
- **Admin Dashboard**: Comprehensive job scraping and database management tools

## 🏗️ Architecture

SkillScopeJob follows a layered architecture with clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                       │
│  streamlit_cv_extraction.py │ admin_utils/streamlit_app.py  │
├─────────────────────────────────────────────────────────────┤
│                     Business Logic                          │
│  profile_job_matcher.py │ cv_job_evaluator.py             │
├─────────────────────────────────────────────────────────────┤
│                     AI/ML Services                          │
│  cv_extraction.py │ data_enrichment_crew.py               │
├─────────────────────────────────────────────────────────────┤
│                    Data Access Layer                        │
│  database_models.py │ indeed_scraper.py                   │
├─────────────────────────────────────────────────────────────┤
│                   External Services                         │
│  Together AI │ Indeed.com │ CrewAI │ JobSpy                │
└─────────────────────────────────────────────────────────────┘
```

### 📁 Project Structure

```
SkillScopeJob/
├── streamlit_cv_extraction.py      # Main Streamlit application
├── cv_extraction.py                # LLM-based CV parsing engine
├── profile_job_matcher.py          # Job matching and search logic
├── cv_job_evaluator.py             # AI-powered CV evaluation system
├── indeed_scraper.py               # Job scraping with python-jobspy
├── data_enrichment_crew.py         # Data enrichment using CrewAI
├── database_models.py              # SQLAlchemy ORM models
├── system_architecture.py          # Architecture visualization tools
├── admin_utils/
│   └── streamlit_app.py            # Admin dashboard for job management
├── ontologies/
│   ├── skill_ontology.csv          # Standardized skills database
│   └── roles_industries_ontology.csv # Job roles and industries
├── indeed_jobs.db                  # SQLite database
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Together AI API key (for AI features)

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SkillScopeJob
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   export TOGETHER_API_KEY="your_together_ai_api_key_here"
   ```
   
   Or create a `.env` file:
   ```
   TOGETHER_API_KEY=your_together_ai_api_key_here
   ```

4. **Initialize the database**
   ```bash
   python -c "from database_models import init_database; init_database()"
   ```

### Getting a Together AI API Key

1. Visit [together.ai](https://together.ai)
2. Sign up for an account
3. Navigate to the API section
4. Generate a new API key
5. Copy and use in your environment configuration

## 📖 Usage

### Main Application

Launch the main career intelligence platform:

```bash
streamlit run streamlit_cv_extraction.py
```

Access the application at `http://localhost:8501`

### Admin Dashboard

Launch the job scraping and management dashboard:

```bash
streamlit run admin_utils/streamlit_app.py
```

Access the admin panel at `http://localhost:8502`

### Core Workflows

#### 1. CV Analysis & Profile Creation
1. Upload your CV (PDF, DOCX, or TXT)
2. Configure AI model and API key
3. Let AI auto-extract and populate your profile
4. Review and customize the extracted information
5. Save your professional profile

#### 2. Job Search & Matching
1. Define job search keywords and preferences
2. Set location and remote work preferences
3. Run intelligent job search with live scraping
4. Review AI-scored job matches with relevance ratings
5. Export results for further analysis

#### 3. CV-Job Evaluation
1. Select jobs from your matches
2. Run comprehensive AI analysis
3. Get detailed compatibility scores
4. Review strengths, gaps, and recommendations
5. Generate personalized improvement plans

#### 4. Data Management (Admin)
1. Configure job search parameters
2. Run batch job scraping operations
3. Monitor database statistics
4. Export job data for analysis

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TOGETHER_API_KEY` | Together AI API key for LLM services | Yes |

### Model Configuration

The application supports multiple AI models:

- **meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo** (Recommended)
- **meta-llama/Llama-3.1-70B-Instruct-Turbo**
- **meta-llama/Llama-3.1-8B-Instruct-Turbo**
- **mistralai/Mixtral-8x7B-Instruct-v0.1**

### Database Configuration

The application uses SQLite by default. The database file (`indeed_jobs.db`) is created automatically in the project root.

## 🔌 API Reference

### Core Components

#### CV Extraction (`cv_extraction.py`)
```python
from cv_extraction import LLMCVExtractor

extractor = LLMCVExtractor(api_key="your_key", model="llama-model")
result = extractor.extract_from_file("path/to/cv.pdf")
```

#### Job Matching (`profile_job_matcher.py`)
```python
from profile_job_matcher import run_profile_job_search

results = run_profile_job_search(profile_data)
```

#### CV Evaluation (`cv_job_evaluator.py`)
```python
from cv_job_evaluator import CVJobEvaluator

evaluator = CVJobEvaluator()
evaluation = evaluator.evaluate_cv_against_specific_jobs(user_id, jobs, profile)
```

#### Job Scraping (`indeed_scraper.py`)
```python
from indeed_scraper import scrape_indeed_jobs

job_count = scrape_indeed_jobs("python developer", "copenhagen, denmark")
```

### Database Models

The application uses SQLAlchemy ORM with the following main models:

- **UserProfile**: User career profiles and preferences
- **JobPosting**: Scraped job postings from Indeed
- **UserJobMatch**: Job-profile matching results
- **CVJobEvaluation**: CV evaluation results

## 🛠️ Development

### Setting Up Development Environment

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install development dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest black flake8  # Additional dev tools
   ```

3. **Run tests**
   ```bash
   python -m pytest tests/  # If test directory exists
   ```

### Code Structure Guidelines

- **Presentation Layer**: Streamlit applications for user interfaces
- **Business Logic**: Core career intelligence and matching algorithms  
- **AI Services**: LLM integration and intelligent analysis
- **Data Layer**: Database models and data access patterns
- **External APIs**: Integration with job boards and AI services

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📊 Key Technologies

### Core Stack
- **Frontend**: Streamlit with custom components
- **Backend**: Python with asyncio support
- **Database**: SQLite with SQLAlchemy ORM
- **AI/ML**: Together AI LLMs, CrewAI for data enrichment

### Major Dependencies
- **streamlit**: Web application framework
- **together**: Together AI SDK for LLM integration
- **python-jobspy**: Job scraping from Indeed
- **sqlalchemy**: Database ORM
- **langchain**: LLM application framework
- **crewai**: Multi-agent AI systems
- **plotly**: Interactive visualizations
- **pandas**: Data manipulation and analysis

### External Services
- **Together AI**: Large Language Model services
- **Indeed.com**: Job posting data source
- **CrewAI**: Multi-agent data enrichment

## 🚨 Troubleshooting

### Common Issues

#### CV Upload Fails
- Verify Together AI API key is set correctly
- Check file format (PDF, DOCX, TXT supported)
- Ensure file is not corrupted or password-protected
- Try a different AI model if extraction fails

#### Job Search Returns No Results
- Check internet connectivity
- Verify job search keywords are not too specific
- Try broader location criteria
- Check if Indeed is accessible from your region

#### Database Errors
- Ensure write permissions in project directory
- Check if SQLite database file is not corrupted
- Try reinitializing database with `init_database()`

#### Performance Issues
- Consider using smaller AI models for faster processing
- Limit job search results to improve response times
- Close other resource-intensive applications

### Error Messages

#### `'<' not supported between instances of 'NoneType' and 'NoneType'`
This sorting error has been fixed in the latest version. Update to the latest code or apply the null-safe sorting patch.

#### `ImportError: No module named 'together'`
Install the Together AI SDK: `pip install together`

#### `API key not found`
Set your Together AI API key in environment variables or directly in the application.

## 🎯 Roadmap

### Version 2.0 (Planned)
- [ ] Multi-language support beyond English/Danish
- [ ] Integration with additional job boards (LinkedIn, Glassdoor)
- [ ] Advanced analytics dashboard with career trends
- [ ] Mobile-responsive design improvements
- [ ] Real-time collaboration features

### Version 1.5 (In Progress)
- [x] Enhanced AI models integration
- [x] Improved job matching algorithms
- [x] Better error handling and user feedback
- [ ] Advanced export capabilities
- [ ] Performance optimizations

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🤝 Support

### Community
- **GitHub Issues**: For bug reports and feature requests
- **Documentation**: Comprehensive inline documentation and comments
- **Examples**: Working examples in the codebase

### Professional Support
For enterprise support, custom integrations, or professional services, please contact the development team.

## 🙏 Acknowledgments

- **Together AI** for providing powerful LLM services
- **Streamlit** for the excellent web application framework
- **python-jobspy** for reliable job scraping capabilities
- **CrewAI** for multi-agent AI system capabilities
- The open-source community for various supporting libraries

---

**SkillScopeJob** - Empowering career decisions with AI intelligence. 🚀

*Built with ❤️ using Python, Streamlit, and cutting-edge AI technologies.*