import json
from datetime import datetime
from pathlib import Path
from elasticsearch import Elasticsearch

class ElasticsearchClient:
    def __init__(self, host="localhost", port=9200, scheme="http"):
        self.es = Elasticsearch([{"host": host, "port": port, "scheme": scheme}]) 
        
        # Paths
        self.elasticsearch_dir = Path("elasticsearch")
        self.mappings_dir = self.elasticsearch_dir / "mappings"
    
    def is_connected(self):
        """Check if connected to Elasticsearch"""
        return self.es.ping()
    
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
    
    # def index_posts(self, posts, index_name):
    #     """Index posts into Elasticsearch"""
    #     # Add collection_date field
    #     now = datetime.now().isoformat()
    #     for post in posts:
    #         post["collection_date"] = now
        
    #     # Bulk index posts
    #     bulk_data = []
    #     for post in posts:
    #         bulk_data.append({"index": {"_index": index_name, "_id": post["post_id"]}})
    #         bulk_data.append(post)
        
    #     if bulk_data:
    #         self.es.bulk(index=index_name, body=bulk_data)
    #         print(f"Indexed {len(posts)} posts into {index_name}")
    
    # def index_comments(self, comments, index_name):
    #     """Index comments into Elasticsearch"""
    #     # Add collection_date field
    #     now = datetime.now().isoformat()
    #     for comment in comments:
    #         comment["collection_date"] = now
        
    #     # Bulk index comments
    #     bulk_data = []
    #     for comment in comments:
    #         bulk_data.append({"index": {"_index": index_name, "_id": comment["comment_id"]}})
    #         bulk_data.append(comment)
        
    #     if bulk_data:
    #         self.es.bulk(index=index_name, body=bulk_data)
    #         print(f"Indexed {len(comments)} comments into {index_name}")
    
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
        
        # Bulk index
        bulk_data = []
        for item in data:
            bulk_data.append({"index": {"_index": index_name, "_id": item[id_field]}})
            bulk_data.append(item)
        
        if bulk_data:
            self.es.bulk(index=index_name, body=bulk_data)
            print(f"Indexed {len(data)} items into {index_name}")