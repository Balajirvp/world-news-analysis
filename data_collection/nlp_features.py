import re
import json
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from transformers import pipeline

class RedditDataEnricher:
    """Class to enrich Reddit data with NER, sentiment, and domain information"""
     
    def __init__(self, ner_model, sentiment_model):
        """Initialize models and reference data"""
        # Initialize NER pipeline
        print("Loading NER model...")

        self.ner_pipeline = pipeline(
            "ner", 
            model=ner_model,
            aggregation_strategy="simple"
        )
        
        # Initialize sentiment analysis pipeline
        print("Loading sentiment analysis model...")
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis", 
            model=sentiment_model
        )
        
        # Region mapping
        self.region_mapping = {
            "North America": [
                "United States", "USA", "U.S.", "U.S.A.", "US", "Canada", "Mexico", 
                "Guatemala", "Belize", "El Salvador", "Honduras", "Nicaragua", 
                "Costa Rica", "Panama"
            ],
            "South America": [
                "Brazil", "Argentina", "Chile", "Colombia", "Peru", "Venezuela", 
                "Ecuador", "Bolivia", "Paraguay", "Uruguay", "Guyana", "Suriname"
            ],
            "Europe": [
                "United Kingdom", "UK", "Britain", "England", "Scotland", "Ireland",
                "France", "Germany", "Italy", "Spain", "Portugal", "Netherlands",
                "Belgium", "Switzerland", "Austria", "Sweden", "Norway", "Denmark",
                "Finland", "Iceland", "Poland", "Russia", "Ukraine", "Greece",
                "Turkey", "Hungary", "Czech Republic", "Romania", "Bulgaria"
            ],
            "Middle East": [
                "Israel", "Palestine", "Iran", "Iraq", "Saudi Arabia", "Yemen",
                "Syria", "Jordan", "Lebanon", "UAE", "United Arab Emirates", 
                "Qatar", "Kuwait", "Bahrain", "Oman"
            ],
            "Africa": [
                "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "Sudan", 
                "South Sudan", "Ethiopia", "Somalia", "Kenya", "Uganda", "Rwanda",
                "Tanzania", "Nigeria", "Ghana", "South Africa", "Zimbabwe", 
                "Democratic Republic of Congo", "DRC", "Congo"
            ],
            "Asia": [
                "China", "Japan", "South Korea", "North Korea", "India", "Pakistan",
                "Bangladesh", "Sri Lanka", "Nepal", "Vietnam", "Thailand", 
                "Indonesia", "Malaysia", "Philippines", "Singapore", "Taiwan",
                "Hong Kong", "Myanmar", "Cambodia", "Laos"
            ],
            "Oceania": [
                "Australia", "New Zealand", "Papua New Guinea", "Fiji", "Solomon Islands",
                "Vanuatu", "Samoa", "Tonga"
            ]
        }
        
        # Create reverse mapping for efficient lookup
        self.country_to_region = {}
        for region, countries in self.region_mapping.items():
            for country in countries:
                self.country_to_region[country.lower()] = region
    
    def extract_domain(self, url):
        """Extract domain from URL"""
        if not url or not isinstance(url, str):
            return None
        try:
            domain = urlparse(url).netloc
            # Remove www. if present
            if domain.startswith('www.'):
                domain = domain[4:]
            # Remove .com if present
            if domain.endswith('.com'):
                domain = domain[:-4]
            return domain
        except:
            return None
    
    def analyze_sentiment(self, text):
        """Calculate sentiment score for text"""
        if not text or not isinstance(text, str) or len(text.strip()) < 5:
            return 0, "neutral"
        
        try:
            # Truncate if too long
            if len(text) > 512:
                text = text[:512]
                
            result = self.sentiment_pipeline(text)[0]
            
            # Convert to score between -1 and 1
            if result['label'] == 'POSITIVE':
                score = result['score'] * 2 - 1  # Transform [0.5,1] to [0,1]
            else:
                score = -result['score'] * 2 + 1  # Transform [0.5,1] to [-1,0]
            
            # Categorize sentiment
            if score > 0.3:
                category = "positive"
            elif score < -0.3:
                category = "negative"
            else:
                category = "neutral"
                
            return score, category
            
        except Exception as e:
            print(f"Error in sentiment analysis: {e}")
            return 0, "neutral"
    
    def extract_entities(self, text):
        """Extract named entities from text"""
        if not text or not isinstance(text, str) or len(text.strip()) < 5:
            return [], [], [], []
        
        try:
            # Truncate if too long
            if len(text) > 512:
                text = text[:512]
                
            # Get entities
            entities = self.ner_pipeline(text)
            
            # Organize by type
            persons = []
            locations = []
            organizations = []
            misc = []
            
            for entity in entities:
                entity_text = entity['word']
                entity_type = entity['entity_group']
                
                if entity_type == 'PER':
                    persons.append(entity_text)
                elif entity_type == 'LOC':
                    locations.append(entity_text)
                elif entity_type == 'ORG':
                    organizations.append(entity_text)
                elif entity_type == 'MISC':
                    misc.append(entity_text)
            
            # Remove duplicates
            persons = list(set(persons))
            locations = list(set(locations))
            organizations = list(set(organizations))
            misc = list(set(misc))
            
            return persons, locations, organizations, misc
            
        except Exception as e:
            print(f"Error in entity extraction: {e}")
            return [], [], [], []
    
    def map_locations_to_regions(self, locations):
        """Map locations to countries and regions"""
        if not locations:
            return []
        
        regions = set()
        
        for location in locations:
            location_lower = location.lower()
            if location_lower in self.country_to_region:
                regions.add(self.country_to_region[location_lower])
        
        # Check for direct region mentions
        location_text = ' '.join(locations).lower()
        for region in self.region_mapping.keys():
            if region.lower() in location_text:
                regions.add(region)
        
        return list(regions)
    
    def enrich_post(self, post):
        """Add enrichment data to a post"""
        enriched_post = post.copy()
        
        # Extract text for analysis
        text = post.get('title', '')
        if 'description' in post and post['description']:
            text += ' ' + post['description']
        
        # Extract domain from URL
        url = post.get('url')
        domain = self.extract_domain(url)
        enriched_post['domain'] = domain
        
        # Sentiment analysis
        sentiment_score, sentiment_category = self.analyze_sentiment(text)
        enriched_post['sentiment_score'] = sentiment_score
        enriched_post['sentiment_category'] = sentiment_category
        
        # Entity extraction
        persons, locations, organizations, misc = self.extract_entities(text)
        enriched_post['persons_mentioned'] = persons
        enriched_post['locations_mentioned'] = locations
        enriched_post['organizations_mentioned'] = organizations
        enriched_post['misc_entities_mentioned'] = misc
        
        # Map locations to regions
        regions = self.map_locations_to_regions(locations)
        enriched_post['regions_mentioned'] = list(regions)
        
        return enriched_post
    
    def enrich_comment(self, comment):
        """Add enrichment data to a comment"""
        enriched_comment = comment.copy()
        
        # Extract text
        text = comment.get('body', '')
        
        # Sentiment analysis
        sentiment_score, sentiment_category = self.analyze_sentiment(text)
        enriched_comment['sentiment_score'] = sentiment_score
        enriched_comment['sentiment_category'] = sentiment_category
        
        return enriched_comment
    
    def process_files(self, posts_file, comments_file, output_posts_file, output_comments_file):
        """Process JSON files and save enriched data"""
        print(f"Processing posts from {posts_file}")
        
        # Process posts
        with open(posts_file, 'r', encoding='utf-8') as f:
            posts = json.load(f)
        
        enriched_posts = []
        for i, post in enumerate(posts):
            if i > 0 and i % 10 == 0:
                print(f"Processed {i}/{len(posts)} posts")
            enriched_post = self.enrich_post(post)
            enriched_posts.append(enriched_post)
        
        # Save enriched posts
        with open(output_posts_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_posts, f, ensure_ascii=False, indent=2)
        
        print(f"Saved enriched posts to {output_posts_file}")
        
        # Process comments
        print(f"Processing comments from {comments_file}")
        with open(comments_file, 'r', encoding='utf-8') as f:
            comments = json.load(f)
        
        enriched_comments = []
        for i, comment in enumerate(comments):
            if i > 0 and i % 100 == 0:
                print(f"Processed {i}/{len(comments)} comments")
            enriched_comment = self.enrich_comment(comment)
            enriched_comments.append(enriched_comment)
        
        # Save enriched comments
        with open(output_comments_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_comments, f, ensure_ascii=False, indent=2)
        
        print(f"Saved enriched comments to {output_comments_file}")
        
        return enriched_posts, enriched_comments