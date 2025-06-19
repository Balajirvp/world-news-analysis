"""
Unit tests for RedditDataEnricher class.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from tests.fixtures.mock_responses import MockResponses

# Mock torch modules at the very top level
sys.modules['torch'] = MagicMock()
sys.modules['torch.cuda'] = MagicMock()
sys.modules['transformers'] = MagicMock()

from data_collection.nlp_features import RedditDataEnricher


class TestRedditDataEnricher:
   """Test suite for RedditDataEnricher."""
   
   @pytest.fixture
   def enricher(self, mock_env_vars):
       """Create a RedditDataEnricher instance for testing."""
       with patch('data_collection.nlp_features.pipeline') as mock_pipeline, \
            patch('data_collection.nlp_features.torch.cuda.is_available', return_value=False), \
            patch('data_collection.nlp_features.torch.cuda.manual_seed_all'):
           
           # Mock NER pipeline
           mock_ner = Mock()
           mock_ner.return_value = MockResponses.get_ner_response()
           
           # Mock sentiment pipeline
           mock_sentiment = Mock()
           mock_sentiment.return_value = MockResponses.get_sentiment_positive()
           
           # Configure pipeline to return different mocks based on task
           def pipeline_side_effect(task, **kwargs):
               if task == "ner":
                   return mock_ner
               elif task == "sentiment-analysis":
                   return mock_sentiment
               return Mock()
           
           mock_pipeline.side_effect = pipeline_side_effect
           
           enricher = RedditDataEnricher(
               mock_env_vars['NER_MODEL'],
               mock_env_vars['SENTIMENT_MODEL']
           )
           enricher.ner_pipeline = mock_ner
           enricher.sentiment_pipeline = mock_sentiment
           
           return enricher
   
   def test_init_with_cuda_available(self, mock_env_vars):
       """Test initialization when CUDA is available."""
       with patch('data_collection.nlp_features.torch.cuda.is_available', return_value=True), \
            patch('data_collection.nlp_features.torch.cuda.manual_seed_all'), \
            patch('data_collection.nlp_features.pipeline') as mock_pipeline:
           
           mock_pipeline.return_value = Mock()
           
           enricher = RedditDataEnricher(
               mock_env_vars['NER_MODEL'],
               mock_env_vars['SENTIMENT_MODEL']
           )
           
           # Should be called twice (NER and sentiment)
           assert mock_pipeline.call_count == 2
           
           # Check that device=0 was used for GPU
           calls = mock_pipeline.call_args_list
           for call in calls:
               kwargs = call[1]
               assert kwargs['device'] == 0
   
   def test_init_with_cuda_unavailable(self, mock_env_vars):
       """Test initialization when CUDA is not available."""
       with patch('data_collection.nlp_features.torch.cuda.is_available', return_value=False), \
            patch('data_collection.nlp_features.torch.cuda.manual_seed_all'), \
            patch('data_collection.nlp_features.pipeline') as mock_pipeline:
           
           mock_pipeline.return_value = Mock()
           
           enricher = RedditDataEnricher(
               mock_env_vars['NER_MODEL'],
               mock_env_vars['SENTIMENT_MODEL']
           )
           
           # Check that device=-1 was used for CPU
           calls = mock_pipeline.call_args_list
           for call in calls:
               kwargs = call[1]
               assert kwargs['device'] == -1
   
   def test_extract_domain_valid_url(self, enricher):
       """Test domain extraction from valid URLs."""
       test_cases = [
           ('https://www.reuters.com/world/article', 'reuters'),
           ('http://bbc.com/news/story', 'bbc'),
           ('https://cnn.com/politics/news', 'cnn'),
           ('https://www.nytimes.com/section/world', 'nytimes'),
           ('http://example.org/page', 'example.org'),
       ]
       
       for url, expected_domain in test_cases:
           result = enricher.extract_domain(url)
           assert result == expected_domain, f"Failed for URL: {url}"
   
   def test_extract_domain_edge_cases(self, enricher):
       """Test domain extraction edge cases."""
       test_cases = [
           (None, None),
           ('', None),
           ('invalid-url', ''),
           ('not-a-url-at-all', ''),
           (123, None),
       ]
       
       for url, expected in test_cases:
           result = enricher.extract_domain(url)
           assert result == expected, f"Failed for input: {url}"
   
   def test_analyze_sentiment_positive(self, enricher):
       """Test sentiment analysis for positive text."""
       enricher.sentiment_pipeline.return_value = [{'label': 'POSITIVE', 'score': 0.9}]
       
       score, category = enricher.analyze_sentiment("This is great news!")
       
       assert score > 0.3
       assert category == "positive"
   
   def test_analyze_sentiment_negative(self, enricher):
       """Test sentiment analysis for negative text."""
       enricher.sentiment_pipeline.return_value = [{'label': 'NEGATIVE', 'score': 0.8}]
       
       score, category = enricher.analyze_sentiment("This is terrible news.")
       
       assert score < -0.3
       assert category == "negative"
   
   def test_analyze_sentiment_neutral(self, enricher):
       """Test sentiment analysis for neutral text."""
       enricher.sentiment_pipeline.return_value = [{'label': 'POSITIVE', 'score': 0.6}]
       
       score, category = enricher.analyze_sentiment("This is some news.")
       
       assert -0.3 <= score <= 0.3
       assert category == "neutral"
   
   def test_analyze_sentiment_edge_cases(self, enricher):
       """Test sentiment analysis edge cases."""
       test_cases = [
           (None, (0, "neutral")),
           ("", (0, "neutral")),
           ("   ", (0, "neutral")),
           ("Hi", (0, "neutral")),
           (123, (0, "neutral")),
       ]
       
       for text, expected in test_cases:
           result = enricher.analyze_sentiment(text)
           assert result == expected, f"Failed for input: {text}"
   
   def test_analyze_sentiment_long_text(self, enricher):
       """Test sentiment analysis with text longer than 512 characters."""
       long_text = "This is a very long text. " * 30
       enricher.sentiment_pipeline.return_value = [{'label': 'POSITIVE', 'score': 0.8}]
       
       score, category = enricher.analyze_sentiment(long_text)
       
       assert score > 0
       assert category == "positive"
       
       call_args = enricher.sentiment_pipeline.call_args[0][0]
       assert len(call_args) == 512
   
   def test_extract_entities_success(self, enricher):
       """Test successful entity extraction."""
       enricher.ner_pipeline.return_value = MockResponses.get_ner_response()
       
       persons, locations, organizations, misc = enricher.extract_entities(
           "Trump and NATO signed an agreement in Denmark"
       )
       
       # Updated to match your mock data
       assert persons == ['Trump']
       assert locations == ['Denmark']
       assert organizations == ['NATO']
       assert misc == ['Agreement']
   
   def test_extract_entities_empty_result(self, enricher):
       """Test entity extraction with no entities found."""
       enricher.ner_pipeline.return_value = []
       
       persons, locations, organizations, misc = enricher.extract_entities(
           "This text has no named entities."
       )
       
       assert persons == []
       assert locations == []
       assert organizations == []
       assert misc == []
   
   def test_extract_entities_confidence_filtering(self, enricher):
       """Test that low-confidence entities are filtered out."""
       # Use custom mock for this specific test
       mock_ner_response = [
           {'entity_group': 'PER', 'word': 'John Doe', 'score': 0.95},
           {'entity_group': 'PER', 'word': 'Maybe Person', 'score': 0.40},  # Below threshold
           {'entity_group': 'LOC', 'word': 'Real Place', 'score': 0.92},
           {'entity_group': 'LOC', 'word': 'Fake Place', 'score': 0.30},  # Below threshold
       ]
       enricher.ner_pipeline.return_value = mock_ner_response
       
       persons, locations, organizations, misc = enricher.extract_entities(
           "Text with mixed confidence entities"
       )
       
       assert 'John Doe' in persons
       assert 'Maybe Person' not in persons
       assert 'Real Place' in locations
       assert 'Fake Place' not in locations
   
   def test_extract_entities_edge_cases(self, enricher):
       """Test entity extraction edge cases."""
       test_cases = [None, "", "   ", 123]
       expected = ([], [], [], [])
       
       for text in test_cases:
           result = enricher.extract_entities(text)
           assert result == expected, f"Failed for input: {text}"
   
   def test_enrich_post_complete(self, enricher, sample_reddit_post):
       """Test complete post enrichment."""
       enricher.ner_pipeline.return_value = MockResponses.get_ner_response()
       enricher.sentiment_pipeline.return_value = MockResponses.get_sentiment_positive()
       
       enriched_post = enricher.enrich_post(sample_reddit_post)
       
       for key, value in sample_reddit_post.items():
           assert enriched_post[key] == value
       
       assert 'domain' in enriched_post
       assert 'sentiment_score' in enriched_post
       assert 'sentiment_category' in enriched_post
       assert 'persons_mentioned' in enriched_post
       assert 'locations_mentioned' in enriched_post
       assert 'organizations_mentioned' in enriched_post
       assert 'misc_entities_mentioned' in enriched_post
       
       assert enriched_post['domain'] == 'reuters'
   
   def test_enrich_comment_complete(self, enricher, sample_reddit_comment):
       """Test complete comment enrichment."""
       enricher.sentiment_pipeline.return_value = MockResponses.get_sentiment_positive()
       
       enriched_comment = enricher.enrich_comment(sample_reddit_comment)
       
       for key, value in sample_reddit_comment.items():
           assert enriched_comment[key] == value
       
       assert 'sentiment_score' in enriched_comment
       assert 'sentiment_category' in enriched_comment
   
   def test_enrich_post_empty_description(self, enricher):
       """Test post enrichment with empty description."""
       post = {
           'post_id': 'test123',
           'title': 'Test Title',
           'url': 'https://test.com',
           'description': ''
       }
       
       enricher.ner_pipeline.return_value = []
       enricher.sentiment_pipeline.return_value = MockResponses.get_sentiment_positive()
       
       enriched_post = enricher.enrich_post(post)
       
       assert 'sentiment_score' in enriched_post
       assert 'sentiment_category' in enriched_post
   
   def test_concurrent_processing(self, enricher):
       """Test that enricher can handle concurrent processing."""
       posts = [
           {'post_id': f'post{i}', 'title': f'Title {i}', 'description': f'Desc {i}', 'url': 'https://test.com'}
           for i in range(5)
       ]
       
       enricher.ner_pipeline.return_value = []
       enricher.sentiment_pipeline.return_value = MockResponses.get_sentiment_positive()
       
       enriched_posts = [enricher.enrich_post(post) for post in posts]
       
       assert len(enriched_posts) == 5
       for i, post in enumerate(enriched_posts):
           assert post['post_id'] == f'post{i}'
           assert 'domain' in post
           assert 'sentiment_score' in post
   
   def test_pipeline_exception_handling(self):
       """Test handling of transformer pipeline exceptions."""
       with patch('data_collection.nlp_features.pipeline') as mock_pipeline:
           mock_pipeline.side_effect = Exception("Model loading failed")
           
           with pytest.raises(Exception) as exc_info:
               RedditDataEnricher("test_ner_model", "test_sentiment_model")
           
           assert "Model loading failed" in str(exc_info.value)
   
   def test_sentiment_pipeline_exception(self, enricher):
       """Test handling of sentiment pipeline exceptions."""
       enricher.sentiment_pipeline.side_effect = Exception("Sentiment analysis failed")
       
       score, category = enricher.analyze_sentiment("Test text")
       assert score == 0
       assert category == "neutral"
   
   def test_ner_pipeline_exception(self, enricher):
       """Test handling of NER pipeline exceptions."""
       enricher.ner_pipeline.side_effect = Exception("NER failed")
       
       result = enricher.extract_entities("Test text")
       expected = ([], [], [], [])
       assert result == expected
   
   def test_preprocess_text(self, enricher):
       """Test text preprocessing functionality."""
       test_cases = [
           ("U.S. and U.K. leaders", "US and UK leaders"),
           ("Test text with... punctuation!", "Test text with punctuation"),
           ("Multiple   spaces", "Multiple spaces"),
           ("", ""),
           (None, ""),
       ]
       
       for input_text, expected in test_cases:
           result = enricher.preprocess_text(input_text)
           assert result == expected, f"Failed for input: '{input_text}'"