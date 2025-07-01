import json
from datetime import datetime
from pathlib import Path
from elasticsearch import Elasticsearch
import os

class ElasticsearchClient:
    def __init__(self):
        """Initialize Elasticsearch client - connects to VPS by default"""
        # VPS Configuration
        self.host = os.getenv('VPS_ELASTICSEARCH_HOST', '140.238.103.154')
        self.port = int(os.getenv('VPS_ELASTICSEARCH_PORT', '9200'))
        self.scheme = os.getenv('VPS_ELASTICSEARCH_SCHEME', 'http')
        self.username = os.getenv('VPS_ELASTICSEARCH_USERNAME', 'elastic')
        self.password = os.getenv('VPS_ELASTICSEARCH_PASSWORD', 'reddit_elastic')
        
        # Create authenticated Elasticsearch client
        self.es = Elasticsearch(
            hosts=[{"host": self.host, "port": self.port, "scheme": self.scheme}],
            basic_auth=(self.username, self.password),
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3
        )
        print(f"✅ Connected to VPS Elasticsearch: {self.scheme}://{self.host}:{self.port}")
        
        # Paths
        self.elasticsearch_dir = Path("elasticsearch")
        self.mappings_dir = self.elasticsearch_dir / "mappings"
    
    def is_connected(self):
        """Check if connected to Elasticsearch"""
        try:
            return self.es.ping()
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def create_indices(self, date_str):
        """Create Elasticsearch indices with mappings"""
        posts_index = f"reddit_worldnews_posts_{date_str}"
        comments_index = f"reddit_worldnews_comments_{date_str}"
        
        # Create posts index if it doesn't exist
        if not self.es.indices.exists(index=posts_index):
            with open(self.mappings_dir / "post_mapping.json", "r") as f:
                mapping = json.load(f)
            self.es.indices.create(index=posts_index, body=mapping)
            print(f"Created index: {posts_index}")
        
        # Create comments index if it doesn't exist
        if not self.es.indices.exists(index=comments_index):
            with open(self.mappings_dir / "comments_mapping.json", "r") as f:
                mapping = json.load(f)
            self.es.indices.create(index=comments_index, body=mapping)
            print(f"Created index: {comments_index}")
        
        return posts_index, comments_index
    
    def load_from_file(self, file_path, index_name, id_field):
        """Load data from a JSON file into an Elasticsearch index"""
        if not Path(file_path).exists():
            print(f"File not found: {file_path}")
            return
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Add collection_date field
        now = datetime.now().isoformat()
        for item in data:
            item["collection_date"] = now
        
        # Use elasticsearch.helpers.bulk with proper format
        if data:
            from elasticsearch.helpers import bulk, BulkIndexError
            try:
                # Format for elasticsearch.helpers.bulk
                actions = []
                for item in data:
                    action = {
                        "_index": index_name,
                        "_id": item[id_field],
                        "_source": item
                    }
                    actions.append(action)
                
                # Use bulk with error handling
                bulk(self.es, actions, raise_on_error=False, raise_on_exception=False)
                print(f"✅ Indexed {len(data)} items into {index_name}")
                    
            except BulkIndexError as e:
                print(f"❌ Bulk indexing errors for {index_name}:")
                for i, error in enumerate(e.errors[:5]):  # Show first 5 errors
                    print(f"  Error {i+1}: {error}")
                print(f"Successfully indexed: {len(data) - len(e.errors)} documents")
                print(f"Failed: {len(e.errors)} documents")
            except Exception as e:
                print(f"❌ Failed to index data into {index_name}: {e}")