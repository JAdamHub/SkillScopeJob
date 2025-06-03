"""
Test script to check jobspy compatibility and supported parameters
"""

import logging
from jobspy import scrape_jobs

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_jobspy():
    """Test basic jobspy functionality"""
    logger.info("Testing basic jobspy functionality...")
    
    try:
        # Most basic test
        result = scrape_jobs(
            site_name=["indeed"],
            search_term="data analyst",
            location="copenhagen, denmark",
            results_wanted=5
        )
        logger.info(f"✅ Basic test successful - found {len(result)} jobs")
        if not result.empty:
            logger.info(f"Columns available: {list(result.columns)}")
            logger.info(f"Sample job: {result.iloc[0]['title']} at {result.iloc[0]['company']}")
        return True
    except Exception as e:
        logger.error(f"❌ Basic test failed: {e}")
        return False

def test_advanced_parameters():
    """Test various parameter combinations"""
    logger.info("Testing advanced parameters...")
    
    base_params = {
        "site_name": ["indeed"],
        "search_term": "software developer", 
        "location": "copenhagen, denmark",
        "results_wanted": 3
    }
    
    # Test parameters one by one
    test_params = [
        ("country_indeed", "denmark"),
        ("job_type", "fulltime"),
        ("is_remote", False),
        ("hours_old", 168),
        ("description_format", "markdown"),
        ("verbose", 1)
    ]
    
    working_params = base_params.copy()
    
    for param_name, param_value in test_params:
        try:
            test_params_dict = working_params.copy()
            test_params_dict[param_name] = param_value
            
            result = scrape_jobs(**test_params_dict)
            logger.info(f"✅ {param_name} parameter works - found {len(result)} jobs")
            working_params[param_name] = param_value
            
        except Exception as e:
            logger.warning(f"❌ {param_name} parameter failed: {e}")
    
    logger.info(f"Working parameters: {list(working_params.keys())}")
    return working_params

def test_danish_locations():
    """Test different Danish location formats"""
    logger.info("Testing Danish location formats...")
    
    locations = [
        "copenhagen, denmark",
        "aarhus, denmark", 
        "aalborg, denmark",
        "denmark",
        "København, Danmark",
        "Aarhus, Danmark"
    ]
    
    working_locations = []
    
    for location in locations:
        try:
            result = scrape_jobs(
                site_name=["indeed"],
                search_term="manager",
                location=location,
                results_wanted=2
            )
            logger.info(f"✅ Location '{location}' works - found {len(result)} jobs")
            working_locations.append(location)
            
        except Exception as e:
            logger.warning(f"❌ Location '{location}' failed: {e}")
    
    return working_locations

def main():
    """Run all tests"""
    logger.info("=" * 50)
    logger.info("JOBSPY COMPATIBILITY TEST")
    logger.info("=" * 50)
    
    # Test 1: Basic functionality
    basic_works = test_basic_jobspy()
    if not basic_works:
        logger.error("Basic jobspy test failed - stopping")
        return
    
    # Test 2: Advanced parameters
    logger.info("\n" + "=" * 30)
    working_params = test_advanced_parameters()
    
    # Test 3: Location formats
    logger.info("\n" + "=" * 30)
    working_locations = test_danish_locations()
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Basic functionality: {'✅ WORKING' if basic_works else '❌ FAILED'}")
    logger.info(f"Working parameters: {list(working_params.keys())}")
    logger.info(f"Working locations: {working_locations}")
    
    # Generate recommended configuration
    logger.info("\n" + "=" * 30)
    logger.info("RECOMMENDED CONFIGURATION:")
    logger.info("=" * 30)
    
    recommended_config = {
        "site_name": ["indeed"],
        "search_term": "YOUR_SEARCH_TERM",
        "location": "copenhagen, denmark",  # Use first working location
        "results_wanted": 50
    }
    
    # Add working parameters
    for param in ["country_indeed", "job_type", "description_format", "verbose"]:
        if param in working_params:
            recommended_config[param] = working_params[param]
    
    for key, value in recommended_config.items():
        logger.info(f"  {key}: {value}")

if __name__ == "__main__":
    main()
