# Reddit WorldNews Pipeline - Testing Suite

This directory contains comprehensive unit and integration tests for the Reddit WorldNews Analytics Pipeline.

## Test Structure

```
tests/
├── conftest.py                    # Pytest configuration and shared fixtures
├── requirements-test.txt          # Test dependencies
├── unit/                         # Unit tests for individual components
│   ├── test_reddit_collector.py  # Reddit API data collection tests
│   ├── test_nlp_features.py      # NLP processing tests
│   ├── test_elasticsearch_client.py # Elasticsearch integration tests
│   ├── test_location_processor.py # Geographic data processing tests
│   ├── test_person_processor.py  # Person name canonicalization tests
│   └── test_utils.py             # Utility functions tests
├── integration/                  # Integration tests
│   └── test_main_pipeline.py     # End-to-end pipeline tests
└── fixtures/                     # Test data and mock responses
    ├── sample_posts.json         # Sample Reddit posts
    ├── sample_comments.json      # Sample Reddit comments
    └── mock_responses.py         # Mock API responses
```

## Getting Started

### 1. Install Test Dependencies

```bash
pip install -r tests/requirements-test.txt
```

### 2. Run All Tests

```bash
pytest tests/
```

### 3. Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only  
pytest tests/integration/

# Specific test file
pytest tests/unit/test_reddit_collector.py

# Specific test method
pytest tests/unit/test_reddit_collector.py::TestRedditDataCollector::test_collect_posts_success
```

## Test Coverage

The test suite aims for 85%+ code coverage. Coverage reports are generated in:

- **HTML Report**: `htmlcov/index.html` (open in browser)
- **Terminal**: Displayed after test execution

To run tests with coverage:

```bash
pytest --cov=data_collection --cov=main --cov-report=html --cov-report=term-missing
```

## Test Categories

### Unit Tests

**Reddit Data Collector** (`test_reddit_collector.py`)
- Reddit API authentication
- Post and comment collection
- Error handling and edge cases
- Data structure validation

**NLP Features** (`test_nlp_features.py`) 
- Named Entity Recognition (NER)
- Sentiment analysis
- Domain extraction
- Text preprocessing
- Model initialization and GPU handling

**Elasticsearch Client** (`test_elasticsearch_client.py`)
- Connection management
- Index creation with mappings
- Bulk data loading
- Error handling

**Location Processor** (`test_location_processor.py`)
- Geocoding API integration
- Country name standardization
- ISO code mapping
- Region classification
- Caching mechanisms

**Person Processor** (`test_person_processor.py`)
- Wikipedia API integration
- Name canonicalization
- Person entity validation
- Deduplication logic

**Utils** (`test_utils.py`)
- Comment metrics calculation
- Post-comment relationship mapping
- Time-based feature engineering
- Discussion thread depth analysis

### Integration Tests

**Main Pipeline** (`test_main_pipeline.py`)
- End-to-end pipeline execution
- Component interaction
- Data flow validation
- Error propagation
- File I/O operations
- Environment variable handling

## Mock Data and Fixtures

### Shared Fixtures (`conftest.py`)

- `mock_env_vars`: Environment variables for testing
- `temp_data_dir`: Temporary directory for file operations
- `sample_reddit_post/comment`: Sample Reddit data structures

### Sample Data (`fixtures/`)

- **sample_posts.json**: Realistic Reddit post data
- **sample_comments.json**: Realistic Reddit comment data  
- **mock_responses.py**: Standardized API response mocks

## Mocking Strategy

Tests use comprehensive mocking to:

1. **Avoid External Dependencies**: No actual API calls to Reddit, Wikipedia, or geocoding services
2. **Ensure Reproducibility**: Consistent test results across environments
3. **Speed Up Execution**: Fast test runs without network delays
4. **Test Error Scenarios**: Simulate API failures and edge cases

### Key Mocked Components

- **Reddit API** (PRAW): Post/comment collection
- **Transformer Models**: NER and sentiment analysis pipelines
- **Geocoding APIs**: Location resolution
- **Wikipedia API**: Person name canonicalization
- **Elasticsearch**: Data indexing operations

## Writing New Tests

### Unit Test Template

```python
"""
Unit tests for YourComponent class.
"""
import pytest
from unittest.mock import Mock, patch
from data_collection.your_component import YourComponent


class TestYourComponent:
    """Test suite for YourComponent."""
    
    @pytest.fixture
    def component(self):
        """Create component instance for testing."""
        return YourComponent()
    
    def test_your_method_success(self, component):
        """Test successful operation."""
        # Arrange
        input_data = {"test": "data"}
        expected_output = {"processed": "data"}
        
        # Act
        result = component.your_method(input_data)
        
        # Assert
        assert result == expected_output
    
    def test_your_method_edge_case(self, component):
        """Test edge case handling."""
        # Test with empty input, None values, etc.
        pass
```

### Best Practices

1. **Test One Thing**: Each test should verify one specific behavior
2. **Use Descriptive Names**: Test names should clearly indicate what's being tested
3. **Follow AAA Pattern**: Arrange, Act, Assert
4. **Mock External Dependencies**: Don't make real API calls
5. **Test Edge Cases**: Empty inputs, None values, API failures
6. **Use Fixtures**: Reuse common test setup
7. **Verify Side Effects**: Check that methods are called with correct parameters

## Performance Considerations

- **Unit tests**: Should run in < 30 seconds total
- **Integration tests**: Should run in < 60 seconds total
- **Use parallel execution** (`-n auto` with pytest-xdist) for faster runs
- **Mock heavy operations** (model loading, API calls)

## Continuous Integration

These tests are designed to run in CI/CD environments:

### GitHub Actions Example

```yaml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pip install -r tests/requirements-test.txt
      - run: pytest --cov=data_collection --cov=main --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure project root is in Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **Missing Dependencies**
   ```bash
   pip install -r tests/requirements-test.txt
   ```

3. **Slow Tests**
   ```bash
   pytest -q
   # Or run specific tests
   pytest tests/unit/test_specific.py
   ```

4. **GPU/CUDA Issues**
   ```bash
   # Run without GPU-dependent tests
   pytest -m "not gpu"
   ```

5. **Coverage Issues**
   ```bash
   # Check which lines are missing coverage
   pytest --cov=data_collection --cov-report=term-missing
   ```

### Debug Mode

For debugging failing tests:

```bash
# Verbose output with print statements
pytest -v -s tests/unit/test_failing.py

# Drop into debugger on failure
pytest --pdb tests/unit/test_failing.py

# Run only failed tests from last run
pytest --lf
```

## Contributing

When adding new features to the pipeline:

1. **Write tests first** (TDD approach)
2. **Maintain coverage** above 85%
3. **Add fixtures** for reusable test data
4. **Update this README** if adding new test categories
5. **Run full test suite** before submitting PRs

### Test Checklist

- [ ] Unit tests for new functions/methods
- [ ] Integration tests for new pipeline steps
- [ ] Mock external dependencies
- [ ] Test error scenarios
- [ ] Update fixtures if needed
- [ ] Verify coverage requirements
- [ ] Update documentation

## Advanced Testing

### Property-Based Testing

For complex data transformations, consider using Hypothesis:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_clean_name_always_returns_string(self, processor, text):
    result = processor.clean_name(text)
    assert isinstance(result, str)
```

### Performance Testing

For performance-critical code:

```python
@pytest.mark.benchmark
def test_process_large_dataset_performance(benchmark):
    result = benchmark(processor.process_posts, large_dataset)
    assert len(result) == len(large_dataset)
```

### Parameterized Tests

For testing multiple scenarios:

```python
@pytest.mark.parametrize("input_text,expected_sentiment", [
    ("Great news!", "positive"),
    ("Terrible situation", "negative"),
    ("Neutral statement", "neutral"),
])
def test_sentiment_analysis(self, enricher, input_text, expected_sentiment):
    score, category = enricher.analyze_sentiment(input_text)
    assert category == expected_sentiment
```