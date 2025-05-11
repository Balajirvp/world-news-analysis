import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import json

from data_collection.reddit_data_collector import RedditDataCollector
from data_collection.elasticsearch_client import ElasticsearchClient
from data_collection.nlp_features import RedditDataEnricher

def main():
    """Main function to orchestrate the data pipeline"""
    print(f"Starting data pipeline at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load environment variables
    load_dotenv()

    # Create data directories if it doesn't exist
    data_dir = Path("data")
    posts_dir = data_dir / "posts"
    comments_dir = data_dir / "comments"

    data_dir.mkdir(exist_ok=True)
    posts_dir.mkdir(exist_ok=True, parents=True)
    comments_dir.mkdir(exist_ok=True, parents=True)

    # Initialize Reddit API client
    reddit_credentials = {
            'client_id': os.getenv("REDDIT_CLIENT_ID"),
            'client_secret': os.getenv("REDDIT_CLIENT_SECRET_ID"),
            'user_agent': os.getenv("REDDIT_USER_AGENT")
        }
    
    reddit_collector = RedditDataCollector(reddit_credentials)

    # Get subreddit name
    subreddit_name = os.getenv("SUBREDDIT", "worldnews")
    
    # Initialize NLP enricher
    ner_model = os.getenv("NER_MODEL")
    sentiment_model = os.getenv("SENTIMENT_MODEL")
    enricher = RedditDataEnricher(ner_model, sentiment_model)

    # Step 1: Collect and enrich data from Reddit
    print("\n--- STEP 1: COLLECTING AND ENRICHING DATA FROM REDDIT ---")
    posts, post_ids = reddit_collector.collect_posts(subreddit_name)  # Remove posts_dir parameter
    
    # Enrich posts
    print("\nEnriching posts with NLP features...")
    enriched_posts = [enricher.enrich_post(post) for post in posts]
    
    # Today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    elasticsearch_date = date_str.replace("-", ".")

    # Save enriched posts
    with open(posts_dir / f"posts_{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(enriched_posts, f, ensure_ascii=False, indent=4)
    print(f"Saved {len(enriched_posts)} enriched posts")

    # Only proceed with comments if we got posts
    if post_ids:
        comments = reddit_collector.collect_comments(post_ids)  # Remove comments_dir parameter
        
        # Enrich comments
        print("\nEnriching comments with NLP features...")
        enriched_comments = [enricher.enrich_comment(comment) for comment in comments]
        
        # Save enriched comments
        with open(comments_dir / f"comments_{date_str}.json", "w", encoding="utf-8") as f:
            json.dump(enriched_comments, f, ensure_ascii=False, indent=4)
        print(f"Saved {len(enriched_comments)} enriched comments")
    
    # Step 2: Load data into Elasticsearch
    print("\n--- STEP 2: LOADING DATA INTO ELASTICSEARCH ---")
    
    # Initialize Elasticsearch client
    es_client = ElasticsearchClient(host="elasticsearch", port=9200, scheme="http")
    
    # Check connection
    if not es_client.is_connected():
        print("Elasticsearch connection failed. Make sure it's running.")
        return
    
    # Create indices
    posts_index, comments_index = es_client.create_indices(elasticsearch_date)
    
    # Load data from files
    posts_file = Path(f"data/posts/posts_{date_str}.json")
    comments_file = Path(f"data/comments/comments_{date_str}.json")
    
    es_client.load_from_file(posts_file, posts_index, "post_id")
    es_client.load_from_file(comments_file, comments_index, "comment_id")
    
    print(f"\nData pipeline completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()