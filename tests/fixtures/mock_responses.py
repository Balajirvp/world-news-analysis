"""
Mock responses for external APIs used in testing.
"""

class MockResponses:
    """Container for all mock API responses."""

    @staticmethod
    def get_ner_response():
        """Mock NER pipeline response."""
        return [
            {'entity_group': 'PER', 'word': 'Trump', 'score': 0.9998, 'start': 0, 'end': 5},
            {'entity_group': 'LOC', 'word': 'Denmark', 'score': 0.9995, 'start': 35, 'end': 42},
            {'entity_group': 'ORG', 'word': 'NATO', 'score': 0.9987, 'start': 70, 'end': 74},
            {'entity_group': 'MISC', 'word': 'Agreement', 'score': 0.9992, 'start': 48, 'end': 57},
        ]

    @staticmethod
    def get_sentiment_positive():
        """Mock positive sentiment response."""
        return [{'label': 'POSITIVE', 'score': 0.8542}]

    @staticmethod
    def get_sentiment_negative():
        """Mock negative sentiment response."""
        return [{'label': 'NEGATIVE', 'score': 0.7823}]

    @staticmethod
    def get_sentiment_neutral():
        """Mock neutral sentiment response."""
        return [{'label': 'POSITIVE', 'score': 0.5123}]  # Low confidence positive = neutral

    @staticmethod
    def get_elasticsearch_bulk_response():
        """Mock Elasticsearch bulk response."""
        return {
            'took': 30,
            'errors': False,
            'items': [
                {'index': {'_index': 'test_index', '_id': 'test123', 'status': 201}}
            ]
        }