import os
import json
import praw
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create data directory if it doesn't exist
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

print(os.getenv("REDDIT_CLIENT_ID"))

reddit = praw.Reddit(**reddit_credentials)

# Get subreddit name
subreddit_name = os.getenv("SUBREDDIT", "worldnews")

def collect_posts():
    """Collect all top posts from r/worldnews in the given day"""
    print(f"Collecting top posts from r/worldnews...")
    
    subreddit = reddit.subreddit("worldnews")
    posts = subreddit.top(time_filter="day")
    
    posts_list = []
    post_ids = []
    
    for post in posts:
        post_data = {
            'post_id': post.id,
            'title': post.title,
            'author': post.author.name if post.author else None,
            'created_utc': post.created_utc,
            'url': post.url,
            'num_comments': post.num_comments,
            'score': post.score,
            'description': post.selftext,
            'upvote_ratio': post.upvote_ratio,
            'post_flair': post.link_flair_text
        }
        posts_list.append(post_data)
        post_ids.append(post.id)
        
    # Save to JSON file with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = posts_dir / f"posts_{date_str}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts_list, f, ensure_ascii=False, indent=4)
    
    print(f"Saved {len(posts_list)} posts to {filename}")
    return post_ids

def collect_comments(post_ids):
    """Collect comments for each post"""
    print(f"Collecting comments for {len(post_ids)} posts...")
    
    all_comments = []
    
    for post_id in post_ids:
        submission = reddit.submission(post_id)
        submission.comments.replace_more(limit=0)  # Load all MoreComments objects
        comments = submission.comments.list()
        
        post_comments = []
        for comment in comments:
            if not hasattr(comment, 'body'):  # Skip any non-comment objects
                continue

            # Remove first 3 characters from parent_id
            parent_id = comment.parent_id[3:] if comment.parent_id and len(comment.parent_id) > 3 else comment.parent_id
                
            comment_data = {
                'comment_id': comment.id,
                'post_id': post_id,
                'body': comment.body,
                'author': comment.author.name if comment.author else None,
                'created_utc': comment.created_utc,
                'parent_id': parent_id,
                'score': comment.score
            }
            post_comments.append(comment_data)
            
        all_comments.extend(post_comments)
        print(f"Collected {len(post_comments)} comments for post {post_id}")
    
    # Save to JSON file with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = comments_dir / f"comments_{date_str}.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=4)
    
    print(f"Saved {len(all_comments)} comments to {filename}")
    return all_comments

def main():
    print(f"Starting data collection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Collect posts and get their IDs
    post_ids = collect_posts()  
    
    # Collect comments for those posts
    if post_ids:
        collect_comments(post_ids)
    
    print(f"Data collection completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()