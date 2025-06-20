"""
Unit tests for WikipediaPersonProcessor class.
"""
import pytest
from unittest.mock import Mock, patch
import json
from data_collection.person_name_mapper import WikipediaPersonProcessor


class TestWikipediaPersonProcessor:
    """Test suite for WikipediaPersonProcessor."""
    
    @pytest.fixture
    def processor(self, temp_data_dir):
        """Create a WikipediaPersonProcessor instance for testing."""
        processor = WikipediaPersonProcessor(cache_dir=str(temp_data_dir))
        return processor
    
    def test_init_creates_cache_files(self, temp_data_dir):
        """Test that initialization creates necessary cache files."""
        processor = WikipediaPersonProcessor(cache_dir=str(temp_data_dir))
        
        # Check that cache attributes exist
        assert hasattr(processor, 'person_cache')
        assert hasattr(processor, 'search_cache')
        assert hasattr(processor, 'categories_cache')
        assert isinstance(processor.person_cache, dict)
        assert isinstance(processor.search_cache, dict)
        assert isinstance(processor.categories_cache, dict)
    
    def test_load_json_existing_file(self, processor, temp_data_dir):
        """Test loading existing JSON cache file."""
        cache_file = temp_data_dir / "test_cache.json"
        test_data = {"person1": "Person One", "person2": "Person Two"}
        cache_file.write_text(json.dumps(test_data))
        
        result = processor._load_json(cache_file)
        
        assert result == test_data
    
    def test_load_json_non_existent_file(self, processor, temp_data_dir):
        """Test loading non-existent cache file returns empty dict."""
        non_existent_file = temp_data_dir / "does_not_exist.json"
        
        result = processor._load_json(non_existent_file)
        
        assert result == {}
    
    def test_save_json_with_metadata(self, processor, temp_data_dir):
        """Test saving data to JSON file with metadata."""
        test_data = {"person1": "Canonical Person", "person2": "Another Person"}
        test_file = temp_data_dir / "test_save.json"
        
        processor._save_json(test_data, test_file)
        
        # Verify file was created and contains correct data
        assert test_file.exists()
        loaded_data = json.loads(test_file.read_text())
        assert "_metadata" in loaded_data
        assert loaded_data["person1"] == "Canonical Person"
        assert loaded_data["person2"] == "Another Person"
    
    def test_clean_name_basic(self, processor):
        """Test basic name cleaning functionality."""
        test_cases = [
            ("John Smith", "John Smith"),
            ("  John Smith  ", "John Smith"),
            ('"John Smith"', "John Smith"),  # Remove quotes
            ("—John Smith—", "John Smith"),  # Remove dashes
            ("John  Smith", "John Smith"),   # Multiple spaces
            ("John\nSmith", "John Smith"),   # Newlines
        ]
        
        for input_name, expected in test_cases:
            result = processor.clean_name(input_name)
            assert result == expected, f"Failed for input: '{input_name}'"
    
    def test_clean_name_edge_cases(self, processor):
        """Test name cleaning edge cases."""
        test_cases = [
            ("", ""),
            ("   ", ""),
            (None, ""),
        ]
        
        for input_name, expected in test_cases:
            result = processor.clean_name(input_name)
            assert result == expected, f"Failed for input: {input_name}"
    
    def test_capitalize_name(self, processor):
        """Test name capitalization."""
        test_cases = [
            ("john smith", "John Smith"),
            ("JOHN SMITH", "John Smith"),
            ("john", "John"),
            ("", ""),
            (None, None),
        ]
        
        for input_name, expected in test_cases:
            result = processor.capitalize_name(input_name)
            assert result == expected, f"Failed for input: {input_name}"
    
    def test_normalize_for_comparison(self, processor):
        """Test diacritics normalization for comparison."""
        test_cases = [
            ("Orbán", "orban"),
            ("Erdoğan", "erdogan"),
            ("Müller", "muller"),
            ("José", "jose"),
            ("Regular Name", "regular name"),
        ]
        
        for input_name, expected in test_cases:
            result = processor.normalize_for_comparison(input_name)
            assert result == expected, f"Failed for input: '{input_name}'"
    
    def test_calculate_name_similarity_score(self, processor):
        """Test name similarity scoring."""
        test_cases = [
            ("Trump", "Donald Trump", 30),  # Search contained in title
            ("Donald Trump", "Trump", 25),  # Title contained in search
            ("Obama", "Barack Obama", 30),  # Partial match
            ("Biden", "Joe Biden", 30),     # Partial match
            ("Smith", "John Smith", 30),    # Common name
            ("Completely Different", "Other Name", 0),  # No match
        ]
        
        for search_name, title, expected_min in test_cases:
            result = processor.calculate_name_similarity_score(search_name, title)
            if expected_min > 0:
                assert result >= expected_min, f"Failed for '{search_name}' vs '{title}': got {result}, expected >= {expected_min}"
            else:
                assert result == 0, f"Failed for '{search_name}' vs '{title}': got {result}, expected 0"
    
    def test_calculate_name_similarity_exact_match(self, processor):
        """Test exact name matching."""
        # Exact matches should get highest score
        result = processor.calculate_name_similarity_score("Donald Trump", "Donald Trump")
        assert result == 50
        
        # Normalized exact matches (diacritics)
        result = processor.calculate_name_similarity_score("Orban", "Orbán")
        assert result == 50
    
    def test_get_categories_with_retry_success(self, processor):
        """Test successful category retrieval with retry."""
        mock_response = {
            'query': {
                'pages': {
                    '123': {
                        'categories': [
                            {'title': 'Category:American politicians'},
                            {'title': 'Category:Living people'},
                            {'title': 'Category:21st-century American people'}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp
            
            categories = processor.get_categories_with_retry("Donald Trump")
            
            expected = ['American politicians', 'Living people', '21st-century American people']
            assert categories == expected
    
    def test_get_categories_with_retry_cached(self, processor):
        """Test category retrieval using cache."""
        cached_categories = ['Cached politician', 'Cached person']
        processor.categories_cache["TestPerson"] = cached_categories
        
        result = processor.get_categories_with_retry("TestPerson")
        
        assert result == cached_categories
    
    def test_get_categories_with_retry_failure(self, processor):
        """Test category retrieval with API failure and retry."""
        with patch('requests.get') as mock_get:
            # Mock failure
            mock_get.side_effect = Exception("API Error")
            
            result = processor.get_categories_with_retry("TestPerson")
            
            assert result == []
            # Should cache empty result
            assert processor.categories_cache["TestPerson"] == []
    
    def test_score_person_by_categories(self, processor):
        """Test person scoring based on categories."""
        test_cases = [
            (['American politicians', 'Living people'], 15),  # President tier
            (['British actors', 'Living people'], 1),         # No political keywords
            (['Ministers of France', 'Living people'], 20),   # Minister tier
            (['Reality television personalities'], -10),       # Negative tier
            ([], 1),  # Empty categories get minimal score
        ]
        
        for categories, expected_min in test_cases:
            score, reasons = processor.score_person_by_categories(categories)
            if expected_min > 0:
                assert score >= expected_min, f"Failed for {categories}: got {score}, expected >= {expected_min}"
            else:
                assert score == expected_min, f"Failed for {categories}: got {score}, expected {expected_min}"
            assert isinstance(reasons, list)
    
    def test_score_candidate(self, processor):
        """Test combined candidate scoring."""
        # High name similarity + political categories = high score
        score, reasons = processor.score_candidate(
            "Trump", 
            "Donald Trump", 
            ['American politicians', 'Presidents of the United States']
        )
        
        assert score > 50  # Should be high due to name match + political role
        assert len(reasons) >= 2  # Should have both name and category reasons
    
    def test_wikipedia_search_living_people_success(self, processor):
        """Test successful Wikipedia search."""
        search_response = {
            'query': {
                'search': [
                    {'title': 'Donald Trump', 'snippet': 'American politician', 'size': 200000}
                ]
            }
        }
        
        categories_response = {
            'query': {
                'pages': {
                    '123': {
                        'categories': [
                            {'title': 'Category:American politicians'},
                            {'title': 'Category:Presidents of the United States'}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            def mock_response_side_effect(url, params=None, **kwargs):
                mock_resp = Mock()
                mock_resp.status_code = 200
                
                # Check params instead of url string
                if params and params.get('list') == 'search':
                    mock_resp.json.return_value = search_response
                elif params and params.get('prop') == 'categories':
                    mock_resp.json.return_value = categories_response
                
                return mock_resp
            
            mock_get.side_effect = mock_response_side_effect
            
            result = processor.wikipedia_search_living_people("Trump")
            
            assert result == "Donald Trump"
    
    def test_wikipedia_search_living_people_no_results(self, processor):
        """Test Wikipedia search with no results."""
        with patch('requests.get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {'query': {'search': []}}
            mock_get.return_value = mock_resp
            
            result = processor.wikipedia_search_living_people("NonExistentPerson")
            
            assert result is None
    
    def test_wikipedia_search_living_people_cached(self, processor):
        """Test Wikipedia search using cached results."""
        # Pre-populate search cache
        search_key = "trump incategory:living_people"
        cached_response = [
            {'title': 'Donald Trump', 'snippet': 'American politician', 'size': 200000}
        ]
        processor.search_cache[search_key] = cached_response
        
        # Mock categories call
        with patch('requests.get') as mock_get:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'query': {
                    'pages': {
                        '123': {
                            'categories': [
                                {'title': 'Category:American politicians'}
                            ]
                        }
                    }
                }
            }
            mock_get.return_value = mock_resp
            
            result = processor.wikipedia_search_living_people("Trump")
            
            assert result == "Donald Trump"
    
    def test_resolve_person_name_with_cache(self, processor):
        """Test person name resolution using cache."""
        processor.person_cache["john smith"] = "John Smith (politician)"
        
        result = processor.resolve_person_name("John Smith")
        
        assert result == "John Smith (politician)"
    
    def test_resolve_person_name_cache_miss(self, processor):
        """Test person name resolution with cache miss."""
        with patch.object(processor, 'wikipedia_search_living_people') as mock_search:
            mock_search.return_value = "Barack Obama"
            
            result = processor.resolve_person_name("Obama")
            
            assert result == "Barack Obama"
            # Should cache the result
            assert processor.person_cache["obama"] == "Barack Obama"
    
    def test_resolve_person_name_no_match(self, processor):
        """Test person name resolution when no match is found."""
        with patch.object(processor, 'wikipedia_search_living_people') as mock_search:
            mock_search.return_value = None
            
            result = processor.resolve_person_name("Unknown Person")
            
            assert result == "Unknown Person"  # Should return capitalized original
            # Should cache the negative result
            assert processor.person_cache["unknown person"] is None
    
    def test_resolve_person_name_empty_input(self, processor):
        """Test person name resolution with empty input."""
        test_cases = ["", "a", None]
        
        for input_name in test_cases:
            result = processor.resolve_person_name(input_name)
            # Should return capitalized version of original
            assert result == processor.capitalize_name(input_name)
    
    def test_simple_deduplicate(self, processor):
        """Test simple deduplication of person names."""
        names = [
            "John Smith",
            "john smith",
            "JOHN SMITH", 
            "Jane Doe",
            "jane doe",
            "Bob Johnson"
        ]
        
        result = processor.simple_deduplicate(names)
        
        # Should keep the best version of each unique name
        assert len(result) == 3
        assert "John Smith" in result
        assert "Jane Doe" in result  
        assert "Bob Johnson" in result
    
    def test_simple_deduplicate_prefers_title_case(self, processor):
        """Test that deduplication prefers properly capitalized names."""
        names = ["john smith", "JOHN SMITH", "John Smith", "john SMITH"]
        
        result = processor.simple_deduplicate(names)
        
        assert result == ["John Smith"]
    
    def test_simple_deduplicate_filters_invalid(self, processor):
        """Test that deduplication filters out invalid names."""
        names = ["John Smith", "a", "123", "Person123", "Valid Name"]
        
        result = processor.simple_deduplicate(names)
        
        # Should filter out single char and names with digits
        expected = ["John Smith", "Valid Name"]
        assert len(result) == 2
        assert "John Smith" in result
        assert "Valid Name" in result
    
    def test_resolve_entities_empty_list(self, processor):
        """Test resolving empty list of entities."""
        result = processor.resolve_entities([])
        
        assert result == []
    
    def test_resolve_entities_with_deduplication(self, processor):
        """Test resolving entities with deduplication."""
        names = ["john smith", "John Smith", "jane doe", "JANE DOE"]
        
        # Mock the resolution
        processor.person_cache = {
            "john smith": "John Smith (politician)",
            "jane doe": "Jane Doe (actress)"
        }
        
        result = processor.resolve_entities(names)
        
        assert len(result) == 2
        assert "John Smith (politician)" in result
        assert "Jane Doe (actress)" in result
    
    def test_update_persons_mentioned_complete_flow(self, processor):
        """Test the complete flow of updating persons mentioned in posts."""
        posts = [
            {
                'post_id': 'post1',
                'persons_mentioned': ['donald trump', 'joe biden', 'barack obama']
            },
            {
                'post_id': 'post2', 
                'persons_mentioned': ['angela merkel', 'emmanuel macron']
            }
        ]
        
        # Mock resolutions
        processor.person_cache = {
            "donald trump": "Donald Trump",
            "joe biden": "Joe Biden", 
            "barack obama": "Barack Obama",
            "angela merkel": "Angela Merkel",
            "emmanuel macron": "Emmanuel Macron"
        }
        
        result = processor.update_persons_mentioned(posts)
        
        assert len(result) == 2
        
        # Check first post
        post1_persons = result[0]['persons_mentioned_updated']
        assert 'Donald Trump' in post1_persons
        assert 'Joe Biden' in post1_persons
        assert 'Barack Obama' in post1_persons
        
        # Check second post
        post2_persons = result[1]['persons_mentioned_updated']
        assert 'Angela Merkel' in post2_persons
        assert 'Emmanuel Macron' in post2_persons
    
    def test_update_persons_mentioned_no_persons(self, processor):
        """Test updating posts with no persons mentioned."""
        posts = [
            {
                'post_id': 'post1',
                'persons_mentioned': []
            }
        ]
        
        result = processor.update_persons_mentioned(posts)
        
        assert len(result) == 1
        assert result[0]['persons_mentioned_updated'] == []
    
    def test_update_persons_mentioned_exception_handling(self, processor):
        """Test exception handling in update_persons_mentioned."""
        posts = [
            {
                'post_id': 'post1',
                'persons_mentioned': ['error_name']
            }
        ]
        
        # Mock resolve_entities to raise exception
        with patch.object(processor, 'resolve_entities') as mock_resolve:
            mock_resolve.side_effect = Exception("Processing error")
            
            result = processor.update_persons_mentioned(posts)
            
            # Should handle exception gracefully
            assert len(result) == 1
            assert result[0]['persons_mentioned_updated'] == []
    
    def test_save_caches(self, processor, temp_data_dir):
        """Test saving all caches to files."""
        # Add test data to caches
        processor.person_cache["test person"] = "Test Person"
        processor.search_cache["test search"] = [{"title": "result"}]
        processor.categories_cache["Test Person"] = ["politician", "person"]
        
        processor.save_caches()
        
        # Verify files were created
        person_file = temp_data_dir / "person_name_mappings.json"
        search_file = temp_data_dir / "wikipedia_search_cache.json" 
        categories_file = temp_data_dir / "wikipedia_categories_cache.json"
        
        assert person_file.exists()
        assert search_file.exists()
        assert categories_file.exists()
        
        # Check content (with metadata)
        person_data = json.loads(person_file.read_text())
        assert person_data["test person"] == "Test Person"
        assert "_metadata" in person_data
    
    def test_get_stats(self, processor):
        """Test getting cache statistics."""
        # Add some test data
        processor.person_cache["person1"] = "Person 1"
        processor.search_cache["search1"] = []
        processor.categories_cache["cat1"] = []
        
        stats = processor.get_stats()
        
        assert "person_mappings" in stats
        assert "search_cache" in stats
        assert "categories_cache" in stats
        assert stats["person_mappings"] >= 1
    
    def test_add_manual_mapping(self, processor):
        """Test adding manual mapping to cache."""
        processor.add_manual_mapping("wrong name", "Correct Name")
        
        assert processor.person_cache["wrong name"] == "Correct Name"
    
    def test_performance_with_large_dataset(self, processor):
        """Test performance with large number of persons."""
        # Create posts with many person mentions
        posts = []
        for i in range(10):
            posts.append({
                'post_id': f'post{i}',
                'persons_mentioned': ['John Smith', 'Jane Doe', 'Bob Wilson']
            })

        # Pre-populate cache to avoid API calls
        processor.person_cache.update({
            'john smith': 'John Smith',
            'jane doe': 'Jane Doe', 
            'bob wilson': 'Bob Wilson'
        })
        
        result = processor.update_persons_mentioned(posts)
        
        assert len(result) == 10
        # Check that processing completed without errors
        for post in result:
            assert 'persons_mentioned_updated' in post
            assert len(post['persons_mentioned_updated']) == 3
    
    def test_cache_persistence_across_instances(self, temp_data_dir):
        """Test that cache persists across processor instances."""
        # Create first processor and add cache data
        processor1 = WikipediaPersonProcessor(cache_dir=str(temp_data_dir))
        processor1.person_cache["test person"] = "Test Person Canonical"
        processor1.save_caches()
        
        # Create second processor - should load cached data
        processor2 = WikipediaPersonProcessor(cache_dir=str(temp_data_dir))
        
        assert "test person" in processor2.person_cache
        assert processor2.person_cache["test person"] == "Test Person Canonical"
    
    def test_debug_search_results(self, processor):
        """Test debug search results functionality."""
        search_response = {
            'query': {
                'search': [
                    {'title': 'Test Person', 'snippet': 'Test snippet', 'size': 10000}
                ]
            }
        }
        
        categories_response = {
            'query': {
                'pages': {
                    '123': {
                        'categories': [
                            {'title': 'Category:Test category'}
                        ]
                    }
                }
            }
        }
        
        with patch('requests.get') as mock_get:
            def mock_response_side_effect(url, **kwargs):
                mock_resp = Mock()
                mock_resp.status_code = 200
                
                if 'list=search' in url:
                    mock_resp.json.return_value = search_response
                elif 'prop=categories' in url:
                    mock_resp.json.return_value = categories_response
                
                return mock_resp
            
            mock_get.side_effect = mock_response_side_effect
            
            # Should not raise exception
            processor.debug_search_results("Test Person")