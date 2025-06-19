"""
Unit tests for LocationProcessor class.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path
from data_collection.location_processor import LocationProcessor
from tests.fixtures.mock_responses import MockResponses


class TestLocationProcessor:
    """Test suite for LocationProcessor."""
    
    @pytest.fixture
    def processor(self, temp_data_dir):
        """Create a LocationProcessor instance for testing."""
        with patch('geopy.geocoders.Nominatim'), \
             patch('geopy.extra.rate_limiter.RateLimiter'):
            
            processor = LocationProcessor(cache_dir=str(temp_data_dir))
            
            # Mock geocoder
            mock_geocoder = Mock()
            processor.geolocator = mock_geocoder
            processor.geocode = mock_geocoder
            
            return processor
    
    def test_init_creates_cache_files(self, temp_data_dir):
        """Test that initialization creates necessary cache directories and files."""
        with patch('geopy.geocoders.Nominatim'), \
             patch('geopy.extra.rate_limiter.RateLimiter'):
            
            processor = LocationProcessor(cache_dir=str(temp_data_dir))
            
            # Check that cache attributes exist
            assert hasattr(processor, 'location_cache')
            assert hasattr(processor, 'region_cache')
            assert hasattr(processor, 'corrections')
            assert isinstance(processor.location_cache, dict)
            assert isinstance(processor.region_cache, dict)
            assert isinstance(processor.corrections, dict)
    
    def test_load_cache_existing_file(self, processor, temp_data_dir):
        """Test loading existing cache file."""
        # Create a cache file with test data
        cache_file = temp_data_dir / "test_cache.json"
        test_data = {"test_key": "test_value", "location1": "country1"}
        cache_file.write_text(json.dumps(test_data))
        
        # Test loading
        result = processor._load_cache(cache_file)
        
        assert result == test_data
    
    def test_load_cache_non_existent_file(self, processor, temp_data_dir):
        """Test loading non-existent cache file returns empty dict."""
        non_existent_file = temp_data_dir / "does_not_exist.json"
        
        result = processor._load_cache(non_existent_file)
        
        assert result == {}
    
    def test_save_cache_sorted(self, processor, temp_data_dir):
        """Test saving data to JSON file with sorting."""
        test_data = {"key1": "value1", "key2": ["list", "data"]}
        test_file = temp_data_dir / "test_save.json"
        
        processor._save_cache_sorted(test_data, test_file)
        
        # Verify file was created and contains correct data
        assert test_file.exists()
        loaded_data = json.loads(test_file.read_text())
        assert "key1" in loaded_data
        assert "key2" in loaded_data
        assert "_metadata" in loaded_data  # Should add metadata
    
    def test_get_country_info_direct_mappings(self, processor):
        """Test direct country mappings."""
        # Test known direct mappings
        test_cases = [
            ("US", ("United States", "US")),
            ("UK", ("United Kingdom", "GB")),
            ("USA", ("United States", "US")),
        ]
        
        for location, expected in test_cases:
            result = processor.get_country_info(location)
            assert result == expected
    
    def test_get_country_info_with_cache(self, processor):
        """Test location resolution using cache."""
        # Pre-populate cache with list format (as used in actual code)
        processor.location_cache["TestCity"] = ["TestCountry", "TC"]
        
        result = processor.get_country_info("TestCity")
        
        assert result == ("TestCountry", "TC")
        # Should not call geocoding
        processor.geocode.assert_not_called()
    
    def test_get_country_info_with_corrections(self, processor):
        """Test location resolution using manual corrections."""
        # Pre-populate corrections
        processor.corrections["WrongName"] = ["CorrectCountry", "CC"]
        
        result = processor.get_country_info("WrongName")
        
        assert result == ("CorrectCountry", "CC")
    
    def test_get_country_info_geocoding_fallback(self, processor):
        """Test location resolution falling back to geocoding."""
        # Setup geocoding mock
        mock_location = Mock()
        mock_location.raw = {
            'lat': '52.5200',
            'lon': '13.4050'
        }
        processor.geocode.return_value = mock_location
        
        # Mock reverse geocoder
        with patch('data_collection.location_processor.rg.search') as mock_rg, \
             patch('data_collection.location_processor.pycountry.countries.get') as mock_country:
            
            mock_rg.return_value = [{'cc': 'DE'}]
            
            mock_country_obj = Mock()
            mock_country_obj.name = 'Germany'
            mock_country_obj.alpha_2 = 'DE'
            mock_country.return_value = mock_country_obj
            
            result = processor.get_country_info("Berlin")
            
            assert result == ("Germany", "DE")
            # Should cache the result
            assert processor.location_cache["Berlin"] == ["Germany", "DE"]
    
    def test_get_country_info_no_resolution(self, processor):
        """Test location that cannot be resolved."""
        processor.geocode.return_value = None
        
        result = processor.get_country_info("UnknownPlace")
        
        assert result == (None, None)
        # Should cache the negative result
        assert processor.location_cache["UnknownPlace"] == [None, None]
    
    def test_get_continent_from_country(self, processor):
        """Test continent/region mapping."""
        with patch('data_collection.location_processor.pc.country_alpha2_to_continent_code') as mock_continent, \
             patch('data_collection.location_processor.pc.convert_continent_code_to_continent_name') as mock_convert:
            
            mock_continent.return_value = 'NA'
            mock_convert.return_value = 'North America'
            
            result = processor.get_continent_from_country("United States", "US")
            
            assert result == "North America"
            # Should cache with readable key
            assert processor.region_cache["US - United States"] == "North America"
    
    def test_get_continent_from_country_middle_east(self, processor):
        """Test that Middle East countries are classified correctly."""
        with patch('data_collection.location_processor.pc.country_alpha2_to_continent_code') as mock_continent, \
             patch('data_collection.location_processor.pc.convert_continent_code_to_continent_name') as mock_convert:
            
            mock_continent.return_value = 'AS'
            mock_convert.return_value = 'Asia'
            
            result = processor.get_continent_from_country("Israel", "IL")
            
            # Should convert Asia to Middle East for Middle East countries
            assert result == "Middle East"
    
    def test_process_locations(self, processor):
        """Test processing a list of locations."""
        # Mock get_country_info responses
        def mock_get_country_info(location):
            mapping = {
                'Paris': ('France', 'FR'),
                'Berlin': ('Germany', 'DE'),
                'Tokyo': ('Japan', 'JP')
            }
            return mapping.get(location, (None, None))
        
        # Mock get_continent_from_country responses
        def mock_get_continent(country, iso):
            mapping = {
                'France': 'Europe',
                'Germany': 'Europe', 
                'Japan': 'Asia'
            }
            return mapping.get(country)
        
        processor.get_country_info = mock_get_country_info
        processor.get_continent_from_country = mock_get_continent
        
        locations = ['Paris', 'Berlin', 'Tokyo']
        updated_names, iso_codes, regions = processor.process_locations(locations)
        
        assert updated_names == ['France', 'Germany', 'Japan']
        assert iso_codes == ['FR', 'DE', 'JP']
        assert regions == ['Europe', 'Asia']  # Deduplicated
    
    def test_process_locations_empty_list(self, processor):
        """Test processing empty list of locations."""
        updated_names, iso_codes, regions = processor.process_locations([])
        
        assert updated_names == []
        assert iso_codes == []
        assert regions == []
    
    def test_process_locations_mixed_results(self, processor):
        """Test processing locations with mixed resolution results."""
        def mock_get_country_info(location):
            mapping = {
                'Paris': ('France', 'FR'),
                'UnknownPlace': (None, None),  # Failed resolution
                'US': ('United States', 'US')
            }
            return mapping.get(location, (None, None))
        
        def mock_get_continent(country, iso):
            mapping = {
                'France': 'Europe',
                'United States': 'North America'
            }
            return mapping.get(country)
        
        processor.get_country_info = mock_get_country_info
        processor.get_continent_from_country = mock_get_continent
        
        locations = ['Paris', 'UnknownPlace', 'US']
        updated_names, iso_codes, regions = processor.process_locations(locations)
        
        # Should only include successfully resolved locations
        assert updated_names == ['France', 'United States']
        assert iso_codes == ['FR', 'US']
        assert regions == ['Europe', 'North America']
    
    def test_process_posts_multiple(self, processor):
        """Test processing multiple posts."""
        posts = [
            {'post_id': 'post1', 'locations_mentioned': ['France']},
            {'post_id': 'post2', 'locations_mentioned': ['Germany', 'Italy']},
            {'post_id': 'post3', 'locations_mentioned': []}
        ]
        
        # Mock process_locations
        def mock_process_locations(locations):
            if not locations:
                return [], [], []
            if locations == ['France']:
                return ['France'], ['FR'], ['Europe']
            if locations == ['Germany', 'Italy']:
                return ['Germany', 'Italy'], ['DE', 'IT'], ['Europe']
            return [], [], []
        
        processor.process_locations = mock_process_locations
        
        processed_posts = processor.process_posts(posts)
        
        assert len(processed_posts) == 3
        
        # Check first post
        assert processed_posts[0]['locations_mentioned_updated'] == ['France']
        assert processed_posts[0]['locations_mentioned_iso_code'] == ['FR']
        assert processed_posts[0]['regions_mentioned'] == ['Europe']
        
        # Check second post
        assert processed_posts[1]['locations_mentioned_updated'] == ['Germany', 'Italy']
        assert processed_posts[1]['locations_mentioned_iso_code'] == ['DE', 'IT']
        assert processed_posts[1]['regions_mentioned'] == ['Europe']
        
        # Check third post
        assert processed_posts[2]['locations_mentioned_updated'] == []
        assert processed_posts[2]['locations_mentioned_iso_code'] == []
        assert processed_posts[2]['regions_mentioned'] == []
    
    def test_save_caches_location_only(self, processor, temp_data_dir):
        """Test saving location cache only."""
        # Add some test data to caches
        processor.location_cache["TestLocation"] = ["TestCountry", "TC"]
        
        processor.save_caches("location")
        
        # Verify location file was created
        location_file = temp_data_dir / "location_cache.json"
        assert location_file.exists()
        
        # Check content
        location_data = json.loads(location_file.read_text())
        assert location_data["TestLocation"] == ["TestCountry", "TC"]
    
    def test_save_caches_region_only(self, processor, temp_data_dir):
        """Test saving region cache only."""
        # Add some test data to caches
        processor.region_cache["US - United States"] = "North America"
        
        processor.save_caches("region")
        
        # Verify region file was created
        region_file = temp_data_dir / "region_cache.json"
        assert region_file.exists()
        
        # Check content
        region_data = json.loads(region_file.read_text())
        assert region_data["US - United States"] == "North America"
    
    def test_direct_mappings_coverage(self, processor):
        """Test various direct mappings from the code."""
        test_cases = [
            ("US", ("United States", "US")),
            ("UK", ("United Kingdom", "GB")),
            ("UAE", ("United Arab Emirates", "AE")),
            ("Beijing", ("China", "CN")),
            ("Moscow", ("Russian Federation", "RU")),
            ("Gaza", ("Palestine, State of", "PS")),
        ]
        
        for location, expected in test_cases:
            result = processor.get_country_info(location)
            assert result == expected, f"Failed for location: {location}"
    
    def test_performance_with_large_dataset(self, processor):
        """Test performance with a large number of posts."""
        # Create posts with direct mappings for speed
        posts = []
        for i in range(100):
            posts.append({
                'post_id': f'post{i}',
                'locations_mentioned': ['US', 'UK', 'France']
            })
        
        # Mock process_locations to use direct mappings
        def mock_process_locations(locations):
            if locations == ['US', 'UK', 'France']:
                return ['United States', 'United Kingdom', 'France'], ['US', 'GB', 'FR'], ['North America', 'Europe']
            return [], [], []
        
        processor.process_locations = mock_process_locations
        
        processed_posts = processor.process_posts(posts)
        
        assert len(processed_posts) == 100
        
        # All posts should have the same processed locations
        for post in processed_posts:
            assert len(post['locations_mentioned_updated']) == 3
            assert 'United States' in post['locations_mentioned_updated']
            assert 'United Kingdom' in post['locations_mentioned_updated']
            assert 'France' in post['locations_mentioned_updated']
    
    def test_cache_persistence_across_instances(self, temp_data_dir):
        """Test that cache persists across different processor instances."""
        # Create first processor and add cache data
        with patch('geopy.geocoders.Nominatim'), \
             patch('geopy.extra.rate_limiter.RateLimiter'):
            
            processor1 = LocationProcessor(cache_dir=str(temp_data_dir))
            processor1.location_cache["TestLocation"] = ["TestCountry", "TC"]
            processor1.save_caches("location")
        
        # Create second processor - should load the cached data
        with patch('geopy.geocoders.Nominatim'), \
             patch('geopy.extra.rate_limiter.RateLimiter'):
            
            processor2 = LocationProcessor(cache_dir=str(temp_data_dir))
            
            assert "TestLocation" in processor2.location_cache
            assert processor2.location_cache["TestLocation"] == ["TestCountry", "TC"]
    
    def test_process_posts_exception_handling(self, processor):
        """Test that process_posts handles exceptions gracefully."""
        posts = [
            {'post_id': 'post1', 'locations_mentioned': ['BadLocation']},
            {'post_id': 'post2', 'locations_mentioned': ['GoodLocation']}
        ]
        
        # Mock process_locations to raise exception for first post
        call_count = 0
        def mock_process_locations(locations):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Processing error")
            return ['GoodCountry'], ['GC'], ['Region']
        
        processor.process_locations = mock_process_locations
        
        processed_posts = processor.process_posts(posts)
        
        # Should still return all posts, with empty fields for failed ones
        assert len(processed_posts) == 2
        assert processed_posts[0]['locations_mentioned_updated'] == []
        assert processed_posts[1]['locations_mentioned_updated'] == ['GoodCountry']
    
    def test_fuzzy_country_search(self, processor):
        """Test fuzzy country name matching."""
        with patch('data_collection.location_processor.pycountry.countries.search_fuzzy') as mock_fuzzy:
            mock_country = Mock()
            mock_country.name = 'Germany'
            mock_country.alpha_2 = 'DE'
            mock_fuzzy.return_value = [mock_country]
            
            result = processor.get_country_info("Deutschland")  # German name for Germany
            
            assert result == ("Germany", "DE")
            mock_fuzzy.assert_called_once_with("Deutschland")