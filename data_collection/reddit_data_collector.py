import praw

class RedditDataCollector:
    def __init__(self, reddit_credentials):
        """Initialize the Reddit API client."""
        self.reddit = praw.Reddit(**reddit_credentials)

    def collect_posts(self, subreddit_name):
        """Collect all top posts from a subreddit in the given day."""
        print(f"Collecting top posts from r/{subreddit_name}...")

        subreddit = self.reddit.subreddit(subreddit_name)
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

        print(f"Collected {len(posts_list)} posts")
        return posts_list, post_ids

    def collect_comments(self, post_ids):
        """Collect comments for each post."""
        print(f"Collecting comments for {len(post_ids)} posts...")

        all_comments = []

        for post_id in post_ids:
            submission = self.reddit.submission(post_id)
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

        print(f"Collected {len(all_comments)} comments total")
        return all_comments