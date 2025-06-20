import re
from urllib.parse import urlparse
from transformers import pipeline
from dotenv import load_dotenv
import torch

load_dotenv()

class RedditDataEnricher:
    """Class to enrich Reddit data with NER, sentiment, and domain information"""
     
    def __init__(self, ner_model, sentiment_model):
        """Initialize models and reference data"""
        # Set random seeds for reproducibility
        torch.cuda.manual_seed_all(42)

        # Initialize NER pipeline
        print("Loading NER model...")

        self.ner_pipeline = pipeline(
            "ner", 
            model=ner_model,
            aggregation_strategy="average",
            device=0 if torch.cuda.is_available() else -1,  # Use GPU if available
            torch_dtype=torch.float32
        )
        
        # Initialize sentiment analysis pipeline
        print("Loading sentiment analysis model...")
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis", 
            model=sentiment_model,
            device=0 if torch.cuda.is_available() else -1,  # Use GPU if available
            torch_dtype=torch.float32
        )
    
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
                entity_score = entity['score']
                
                if entity_type == 'PER' and entity_score > 0.9: 
                    persons.append(entity_text)
                elif entity_type == 'LOC' and entity_score > 0.9:
                    locations.append(entity_text)
                elif entity_type == 'ORG' and entity_score > 0.9:
                    organizations.append(entity_text)
                elif entity_type == 'MISC' and entity_score > 0.9:
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

    def preprocess_text(self, text):
        """Clean text for better person/location NER performance"""
        if not text:
            return ""
        
        # Remove all punctuation except hyphens
        # This converts U.S. → US, U.K. → UK, etc.
        text = re.sub(r"[^\w\s'’,\-]", '', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def enrich_post(self, post):
        """Add enrichment data to a post"""
        enriched_post = post.copy()
        
        # Extract text for analysis
        text = post.get('title', '')
        # Extract domain from URL
        url = post.get('url')
        domain = self.extract_domain(url)
        enriched_post['domain'] = domain
        
        # Sentiment analysis
        sentiment_score, sentiment_category = self.analyze_sentiment(text)
        enriched_post['sentiment_score'] = sentiment_score
        enriched_post['sentiment_category'] = sentiment_category

        processed_text = self.preprocess_text(text)  # Clean text for better NER performance
        
        # Entity extraction
        persons, locations, organizations, misc = self.extract_entities(processed_text)
        enriched_post['persons_mentioned'] = persons
        enriched_post['locations_mentioned'] = locations
        enriched_post['organizations_mentioned'] = organizations
        enriched_post['misc_entities_mentioned'] = misc
        
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