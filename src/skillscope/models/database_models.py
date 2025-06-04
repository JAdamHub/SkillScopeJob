import enum
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, UniqueConstraint, Index, Enum as SQLAlchemyEnum, or_, and_, desc, func as sql_func
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from sqlalchemy.sql import func
import json # For handling fields that might remain JSON

Base = declarative_base()

# Enum for job status - example, can be extended
class JobStatusEnum(enum.Enum):
    active = "active"
    expired = "expired"
    filled = "filled"

class JobPosting(Base):
    __tablename__ = 'job_postings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text)
    company = Column(Text)
    company_url = Column(Text)
    job_url = Column(Text, unique=True) # Job URL should be unique
    location = Column(Text)
    is_remote = Column(Boolean)
    job_type = Column(Text) # Consider Enum here too, if types are fixed
    description = Column(Text)
    date_posted = Column(DateTime) # Use DateTime for 'DATE' for consistency
    company_industry = Column(Text)
    company_description = Column(Text)
    company_logo = Column(Text)
    scraped_timestamp = Column(DateTime, default=func.now())
    search_term = Column(Text)
    search_location = Column(Text)
    search_job_type = Column(Text)
    search_is_remote = Column(Boolean)
    job_status = Column(SQLAlchemyEnum(JobStatusEnum), default=JobStatusEnum.active)
    refresh_count = Column(Integer, default=1)
    job_freshness = Column(Text) # Can possibly be calculated or be an Enum
    enrichment_status = Column(Text) # Can possibly be an Enum
    user_profile_match = Column(Float) # Match score

    # Relations (if relevant for job_postings directly)
    # E.g. if a job_evaluation_detail links directly here
    evaluation_details = relationship("JobEvaluationDetail", back_populates="job_posting")

    __table_args__ = (
        Index('idx_job_postings_title', 'title'),
        Index('idx_job_postings_company', 'company'),
        Index('idx_job_postings_location', 'location'),
        Index('idx_job_postings_scraped_timestamp', 'scraped_timestamp'),
    )

class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_session_id = Column(String, unique=True, index=True, nullable=False)
    
    # Unpacked fields from profile_data
    submission_timestamp = Column(DateTime)
    user_id_input = Column(Text) # If it's a separate ID from session_id
    overall_field = Column(String)
    personal_description = Column(Text)
    total_experience = Column(String) # E.g. "3-5 years"
    remote_openness = Column(String)
    analysis_preference = Column(String)
    
    # For fields that were lists/JSON before, but now are relations:
    target_roles = relationship("UserProfileTargetRole", back_populates="user_profile", cascade="all, delete-orphan")
    keywords = relationship("UserProfileKeyword", back_populates="user_profile", cascade="all, delete-orphan")
    skills = relationship("UserProfileSkill", back_populates="user_profile", cascade="all, delete-orphan")
    languages = relationship("UserProfileLanguage", back_populates="user_profile", cascade="all, delete-orphan")
    job_types = relationship("UserProfileJobType", back_populates="user_profile", cascade="all, delete-orphan")
    preferred_locations = relationship("UserProfileLocation", back_populates="user_profile", cascade="all, delete-orphan")
    
    education_entries = relationship("UserEducation", back_populates="user_profile", cascade="all, delete-orphan")
    experience_entries = relationship("UserExperience", back_populates="user_profile", cascade="all, delete-orphan")
    
    cv_evaluations = relationship("CVJobEvaluation", back_populates="user_profile")

    # Old profile_data - can be kept temporarily during migration or removed
    # profile_data = Column(Text) 
    
    created_timestamp = Column(DateTime, default=func.now())
    last_search_timestamp = Column(DateTime, onupdate=func.now())


# Intermediate tables for UserProfile many-to-many relations
class UserProfileTargetRole(Base):
    __tablename__ = 'user_profile_target_roles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    role_or_industry_name = Column(String, nullable=False)
    user_profile = relationship("UserProfile", back_populates="target_roles")
    __table_args__ = (Index('idx_user_profile_target_roles_profile_id', 'user_profile_id'),)

class UserProfileKeyword(Base):
    __tablename__ = 'user_profile_keywords'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    keyword = Column(String, nullable=False)
    user_profile = relationship("UserProfile", back_populates="keywords")
    __table_args__ = (Index('idx_user_profile_keywords_profile_id', 'user_profile_id'),)

class UserProfileSkill(Base):
    __tablename__ = 'user_profile_skills'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    skill_name = Column(String, nullable=False) # Consider a separate Skill table if skills have more data
    user_profile = relationship("UserProfile", back_populates="skills")
    __table_args__ = (Index('idx_user_profile_skills_profile_id', 'user_profile_id'),)

class UserProfileLanguage(Base):
    __tablename__ = 'user_profile_languages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    language_name = Column(String, nullable=False)
    user_profile = relationship("UserProfile", back_populates="languages")
    __table_args__ = (Index('idx_user_profile_languages_profile_id', 'user_profile_id'),)

class UserProfileJobType(Base):
    __tablename__ = 'user_profile_job_types'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    job_type_name = Column(String, nullable=False)
    user_profile = relationship("UserProfile", back_populates="job_types")
    __table_args__ = (Index('idx_user_profile_job_types_profile_id', 'user_profile_id'),)

class UserProfileLocation(Base):
    __tablename__ = 'user_profile_locations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    location_name = Column(String, nullable=False)
    user_profile = relationship("UserProfile", back_populates="preferred_locations")
    __table_args__ = (Index('idx_user_profile_locations_profile_id', 'user_profile_id'),)

class UserEducation(Base):
    __tablename__ = 'user_education'
    id = Column(Integer, primary_key=True, autoincrement=True) # Or use profile_id + a unique identifier within the profile
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    degree = Column(String)
    field_of_study = Column(String)
    institution = Column(String)
    graduation_year = Column(String) # Or Integer, if format is consistent
    user_profile = relationship("UserProfile", back_populates="education_entries")
    __table_args__ = (Index('idx_user_education_profile_id', 'user_profile_id'),)

class UserExperience(Base):
    __tablename__ = 'user_experience'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_profile_id = Column(Integer, ForeignKey('user_profiles.id'), nullable=False)
    job_title = Column(String)
    company = Column(String)
    years_in_role = Column(Float) # Or String if there are "2.25 years" etc. Float is better for calculations
    skills_responsibilities = Column(Text)
    user_profile = relationship("UserProfile", back_populates="experience_entries")
    __table_args__ = (Index('idx_user_experience_profile_id', 'user_profile_id'),)

class CVJobEvaluation(Base):
    __tablename__ = 'cv_job_evaluations' # Confirm table name

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_session_id = Column(String, ForeignKey('user_profiles.user_session_id'), index=True, nullable=False) # Link to user_profiles
    evaluation_timestamp = Column(DateTime, default=func.now())
    jobs_evaluated = Column(Integer)
    average_match_score = Column(Float) # Overall average

    # For storing the rest of the summary part of JSON, if it's complex/variable
    # summary_details_json = Column(Text) # Stores e.g. score_distribution as JSON string

    user_profile = relationship("UserProfile", back_populates="cv_evaluations")
    evaluation_details = relationship("JobEvaluationDetail", back_populates="cv_job_evaluation", cascade="all, delete-orphan")

class JobEvaluationDetail(Base):
    __tablename__ = 'job_evaluation_details'
    id = Column(Integer, primary_key=True, autoincrement=True)
    cv_job_evaluation_id = Column(Integer, ForeignKey('cv_job_evaluations.id'), nullable=False)
    job_posting_id = Column(Integer, ForeignKey('job_postings.id'), nullable=True) # Can be null if job doesn't exist/match directly

    # Fields from "evaluations" array in JSON
    job_number = Column(Integer) # If still relevant
    job_title_evaluated = Column(Text) # Title as it was evaluated (can differ from job_postings.title)
    company_evaluated = Column(Text) # Likewise for company

    match_score = Column(Float) # Individual match score for this job
    overall_fit = Column(String)
    seniority_match = Column(String)
    experience_gap = Column(Text)
    reality_check = Column(Text)
    strengths = Column(Text)
    critical_gaps = Column(Text)
    minor_gaps = Column(Text)
    recommendations = Column(Text)
    likelihood = Column(String)
    
    # Raw JSON for this specific job evaluation, if there are additional variable fields
    # raw_evaluation_item_json = Column(Text)

    cv_job_evaluation = relationship("CVJobEvaluation", back_populates="evaluation_details")
    job_posting = relationship("JobPosting", back_populates="evaluation_details")

    __table_args__ = (
        Index('idx_job_eval_details_cv_eval_id', 'cv_job_evaluation_id'),
        Index('idx_job_eval_details_job_id', 'job_posting_id'),
    )

# Example engine setup (should be in your database initialization file)
# DATABASE_URL = "sqlite:///./data/databases/indeed_jobs.db"
# engine = create_engine(DATABASE_URL)
# Base.metadata.create_all(engine) # To create the tables

DATABASE_URL = "sqlite:///./data/databases/indeed_jobs.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} # Necessary for SQLite with multi-threaded apps like Streamlit
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# It's generally recommended to manage table creation/migrations separately
# (e.g., using Alembic or by running a setup script once)
# rather than calling create_all() on import.
# If you need to ensure tables are created when the app starts and models are defined,
# you can uncomment the line below, but be mindful of its implications.
Base.metadata.create_all(bind=engine) # Ensure all tables are created based on models
