#!/usr/bin/env python3
import json
import requests
from pathlib import Path

class SimpleElasticsearchClient:
    def __init__(self, host="localhost", port=9200, scheme="http"):
        self.base_url = f"{scheme}://{host}:{port}"
    
    def is_connected(self):
        try:
            response = requests.get(f"{self.base_url}/_cluster/health")
            return response.status_code == 200
        except:
            return False
    
    def index_exists(self, index_name):
        response = requests.head(f"{self.base_url}/{index_name}")
        return response.status_code == 200
    
    def delete_index(self, index_name):
        response = requests.delete(f"{self.base_url}/{index_name}")
        return response.status_code == 200
    
    def create_index(self, index_name, mapping):
        response = requests.put(
            f"{self.base_url}/{index_name}",
            headers={'Content-Type': 'application/json'},
            json=mapping
        )
        return response.status_code == 200
    
    def load_from_file(self, file_path, index_name, id_field):
        if not Path(file_path).exists():
            print(f"File not found: {file_path}")
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Bulk upload
        bulk_data = []
        for item in data:
            bulk_data.append(json.dumps({"index": {"_index": index_name, "_id": item[id_field]}}))
            bulk_data.append(json.dumps(item))
        
        bulk_body = '\n'.join(bulk_data) + '\n'
        
        response = requests.post(
            f"{self.base_url}/_bulk",
            headers={'Content-Type': 'application/x-ndjson'},
            data=bulk_body
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('errors'):
                print(f"Some errors occurred during indexing")
                return False
            print(f"✅ Successfully uploaded {len(data)} items to {index_name}")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            return False

def main():
    print("🚀 Starting proper reindexing with mappings...")
    
    # Initialize Elasticsearch client
    es_client = SimpleElasticsearchClient()
    
    # Check connection
    if not es_client.is_connected():
        print("❌ Failed to connect to Elasticsearch")
        return
    
    print("✅ Connected to Elasticsearch")
    
    # Load mapping files
    with open("elasticsearch/mappings/post_mapping.json") as f:
        posts_mapping = json.load(f)
    
    with open("elasticsearch/mappings/comments_mapping.json") as f:
        comments_mapping = json.load(f)
    
    print("✅ Loaded mapping files")
    
    # Get all data files
    post_files = list(Path("data/posts").glob("posts_*.json"))
    comment_files = list(Path("data/comments").glob("comments_*.json"))
    
    print(f"📁 Found {len(post_files)} post files and {len(comment_files)} comment files")
    
    # Process posts
    print("\n🔄 Processing Posts...")
    for i, post_file in enumerate(sorted(post_files), 1):
        date_str = post_file.stem.replace("posts_", "").replace("-", ".")
        posts_index = f"reddit_worldnews_posts_{date_str}"
        
        print(f"[{i}/{len(post_files)}] Processing {posts_index}")
        
        try:
            # Delete existing index
            if es_client.index_exists(posts_index):
                print(f"  🗑️  Deleting existing index: {posts_index}")
                es_client.delete_index(posts_index)
            
            # Create index with mapping
            print(f"  🏗️  Creating index with mapping: {posts_index}")
            if not es_client.create_index(posts_index, posts_mapping):
                print(f"  ❌ Failed to create index: {posts_index}")
                continue
            
            # Load data
            print(f"  📊 Loading data into: {posts_index}")
            if not es_client.load_from_file(post_file, posts_index, "post_id"):
                print(f"  ❌ Failed to load data into: {posts_index}")
                continue
                
        except Exception as e:
            print(f"  ❌ Error processing {posts_index}: {str(e)}")
            continue
    
    # Process comments
    print("\n🔄 Processing Comments...")
    for i, comment_file in enumerate(sorted(comment_files), 1):
        date_str = comment_file.stem.replace("comments_", "").replace("-", ".")
        comments_index = f"reddit_worldnews_comments_{date_str}"
        
        print(f"[{i}/{len(comment_files)}] Processing {comments_index}")
        
        try:
            # Delete existing index
            if es_client.index_exists(comments_index):
                print(f"  🗑️  Deleting existing index: {comments_index}")
                es_client.delete_index(comments_index)
            
            # Create index with mapping
            print(f"  🏗️  Creating index with mapping: {comments_index}")
            if not es_client.create_index(comments_index, comments_mapping):
                print(f"  ❌ Failed to create index: {comments_index}")
                continue
            
            # Load data
            print(f"  📊 Loading data into: {comments_index}")
            if not es_client.load_from_file(comment_file, comments_index, "comment_id"):
                print(f"  ❌ Failed to load data into: {comments_index}")
                continue
                
        except Exception as e:
            print(f"  ❌ Error processing {comments_index}: {str(e)}")
            continue
    
    print("\n🎉 Reindexing completed with proper mappings!")
    print("🔍 Check your Kibana dashboard - errors should be resolved!")

if __name__ == "__main__":
    main()
