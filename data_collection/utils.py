from collections import defaultdict

class Utils:
    """Utility functions for Reddit data processing."""

    @staticmethod
    def add_comment_metrics(posts, comments):
        """
        Adds comment-related metrics to each post in the posts list.
        Modifies the posts in-place and also returns them.
        """
        comments_by_post = defaultdict(list)
        for comment in comments:
            post_id = comment.get("post_id")
            if post_id:
                comments_by_post[post_id].append(comment)

        for post in posts:
            post_id = post.get("post_id")
            post_created_utc = post.get("created_utc")
            post_comments = comments_by_post.get(post_id, [])

            # Basic counts
            post["comment_count"] = len(post_comments)
            # Find the top comment by score
            if post_comments:
                top_comment = max(post_comments, key=lambda c: c.get("score", float('-inf')))
                post["top_comment"] = top_comment
            else:
                post["top_comment"] = None

            # Time-based features
            if post_comments and post_created_utc:
                comment_times = [c.get("created_utc") for c in post_comments if c.get("created_utc") is not None]
                comment_times = sorted(comment_times)
                if comment_times:
                    # Time to First Comment (minutes)
                    time_to_first_comment = (comment_times[0] - post_created_utc) / 60
                    post["time_to_first_comment_min"] = round(time_to_first_comment, 2)

                    # Time of Last Comment (timestamp)
                    # post["last_comment_time"] = comment_times[-1]

                    # Post Discussion Duration (minutes)
                    post["discussion_duration_min"] = round((comment_times[-1] - post_created_utc) / 60, 2)
                else:
                    post["time_to_first_comment_min"] = None
                    post["last_comment_time"] = None
                    post["discussion_duration_min"] = None

                # Comment Time Buckets
                # Hourly buckets for first 6 hours, then 6-12h, 12-24h, >24h
                buckets = {f"comments_{i}_{i+1}h": 0 for i in range(6)}
                buckets.update({
                    "comments_6_12h": 0,
                    "comments_12_24h": 0,
                    "comments_24h_plus": 0
                })
                for c_time in comment_times:
                    delta_min = (c_time - post_created_utc) / 60
                    delta_hr = delta_min / 60
                    if 0 <= delta_hr < 1:
                        buckets["comments_0_1h"] += 1
                    elif 1 <= delta_hr < 2:
                        buckets["comments_1_2h"] += 1
                    elif 2 <= delta_hr < 3:
                        buckets["comments_2_3h"] += 1
                    elif 3 <= delta_hr < 4:
                        buckets["comments_3_4h"] += 1
                    elif 4 <= delta_hr < 5:
                        buckets["comments_4_5h"] += 1
                    elif 5 <= delta_hr < 6:
                        buckets["comments_5_6h"] += 1
                    elif 6 <= delta_hr < 12:
                        buckets["comments_6_12h"] += 1
                    elif 12 <= delta_hr < 24:
                        buckets["comments_12_24h"] += 1
                    elif delta_hr >= 24:
                        buckets["comments_24h_plus"] += 1
                post.update(buckets)
            else:
                post["time_to_first_comment_min"] = None
                post["discussion_duration_min"] = None
                for i in range(6):
                    post[f"comments_{i}_{i+1}h"] = 0
                post["comments_6_12h"] = 0
                post["comments_12_24h"] = 0
                post["comments_24h_plus"] = 0

            # Engagement Features
            unique_commenters = set()
            sentiment_scores = []
            for comment in post_comments:
                author = comment.get("author")
                if author:
                    unique_commenters.add(author)
                sentiment = comment.get("sentiment_score")
                if sentiment is not None:
                    sentiment_scores.append(sentiment)
            post["unique_commenters"] = len(unique_commenters)
            post["avg_comment_sentiment"] = (
                round(sum(sentiment_scores) / len(sentiment_scores), 4) if sentiment_scores else None
            )

            # Discussion Depth Features
            # Compute comment depths using parent_id chain
            comment_id_map = {c["comment_id"]: c for c in post_comments if "comment_id" in c}
            depths = {}

            def get_depth(comment):
                cid = comment.get("comment_id")
                if cid in depths:
                    return depths[cid]
                parent_id = comment.get("parent_id")
                post_id = comment.get("post_id")
                # If parent_id refers to the post, depth is 1
                if not parent_id or parent_id == post_id:
                    depths[cid] = 1
                    return 1
                # If parent_id refers to another comment
                parent_comment = comment_id_map.get(parent_id)
                if parent_comment:
                    d = get_depth(parent_comment) + 1
                    depths[cid] = d
                    return d
                else:
                    # Parent comment not found, treat as top-level
                    depths[cid] = 1
                    return 1

            all_depths = []
            for comment in post_comments:
                if "comment_id" in comment and "parent_id" in comment:
                    depth = get_depth(comment)
                    all_depths.append(depth)
            post["max_comment_depth"] = max(all_depths) if all_depths else 0
            post["avg_comment_depth"] = round(sum(all_depths) / len(all_depths), 2) if all_depths else 0

        return posts

    
    @staticmethod
    def add_post_metrics(posts, comments):
        """
        Adds post-related metrics to each comment in the comments list.
        Modifies the comments in-place and also returns them.
        """
        # Build a mapping from post_id to post
        post_map = {post.get("post_id"): post for post in posts}

        # Build a mapping from comment_id to comment for depth calculation
        comment_id_map = {c.get("comment_id"): c for c in comments if c.get("comment_id")}
        
        for comment in comments:
            post_id = comment.get("post_id")
            post = post_map.get(post_id)
            if post:
                post_created_utc = post.get("created_utc")
                comment_created_utc = comment.get("created_utc")
                # Time from post in minutes/hours
                if post_created_utc is not None and comment_created_utc is not None:
                    delta_min = (comment_created_utc - post_created_utc) / 60
                    delta_hr = delta_min / 60
                    comment["time_from_post_in_minutes"] = round(delta_min, 2)
                    comment["time_from_post_in_hours"] = round(delta_hr, 2)
                    # Time bucket
                    if 0 <= delta_hr < 1:
                        comment["time_bucket"] = "0-1h"
                    elif 1 <= delta_hr < 2:
                        comment["time_bucket"] = "1-2h"
                    elif 2 <= delta_hr < 3:
                        comment["time_bucket"] = "2-3h"
                    elif 3 <= delta_hr < 4:
                        comment["time_bucket"] = "3-4h"
                    elif 4 <= delta_hr < 5:
                        comment["time_bucket"] = "4-5h"
                    elif 5 <= delta_hr < 6:
                        comment["time_bucket"] = "5-6h"
                    elif 6 <= delta_hr < 12:
                        comment["time_bucket"] = "6-12h"
                    elif 12 <= delta_hr < 24:
                        comment["time_bucket"] = "12-24h"
                    elif delta_hr >= 24:
                        comment["time_bucket"] = "24h+"
                    else:
                        comment["time_bucket"] = None
                else:
                    comment["time_from_post_in_minutes"] = None
                    comment["time_from_post_in_hours"] = None
                    comment["time_bucket"] = None

                # Post sentiment, score, comment count
                comment["post_sentiment"] = post.get("sentiment_score")
                comment["post_score"] = post.get("score")
                comment["post_comment_count"] = post.get("num_comments")
            else:
                comment["time_from_post_in_minutes"] = None
                comment["time_from_post_in_hours"] = None
                comment["time_bucket"] = None
                comment["post_sentiment"] = None
                comment["post_score"] = None
                comment["post_comment_count"] = None

            # Comment depth and is_top_level
            comment_id = comment.get("comment_id")
            parent_id = comment.get("parent_id")
            # Top-level if parent_id refers to the post (parent_id == post_id)
            if parent_id and post_id and parent_id == post_id:
                comment["comment_depth"] = 1
                comment["is_top_level"] = True
            else:
                # Calculate depth by traversing parent chain
                depth = 1
                current_parent = parent_id
                while current_parent and current_parent in comment_id_map:
                    parent_comment = comment_id_map.get(current_parent)
                    if parent_comment:
                        depth += 1
                        current_parent = parent_comment.get("parent_id")
                        # Stop if parent_id refers to the post
                        if current_parent == post_id:
                            break
                    else:
                        break
                comment["comment_depth"] = depth
                comment["is_top_level"] = (depth == 1)
        return comments