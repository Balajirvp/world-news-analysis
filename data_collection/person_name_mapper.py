import json
import re
import requests
import logging
import time
import unicodedata
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class WikipediaPersonProcessor:
    """
    Wikipedia-based person name processor with comprehensive caching, scoring, and name similarity.
    Uses living people search + categories API + name matching for accurate political figure identification.
    """
    
    def __init__(self, cache_dir="data"):
        """Initialize Wikipedia person processor"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Cache files
        self.person_cache_file = self.cache_dir / "person_name_mappings.json"
        self.search_cache_file = self.cache_dir / "wikipedia_search_cache.json"
        self.categories_cache_file = self.cache_dir / "wikipedia_categories_cache.json"
        
        # Load caches
        self.person_cache = self._load_json(self.person_cache_file)
        self.search_cache = self._load_json(self.search_cache_file)
        self.categories_cache = self._load_json(self.categories_cache_file)
        
        print(f"Loaded {len(self.person_cache)} person mappings from cache")
        print(f"Loaded {len(self.search_cache)} search cache entries")
        print(f"Loaded {len(self.categories_cache)} categories cache entries")
        
        # Comprehensive scoring system based on our discussion
        self.scoring_keywords = {
            # Tier 1: Highest Political Authority (+25 points)
            'president': 25, 'prime minister': 25, 'heads of state': 25, 'heads of government': 25,
            'monarch': 25, 'king': 25, 'queen': 25, 'emperor': 25, 'dictator': 25, 'supreme leader': 25, "pope": 25,
            
            # Tier 2: High Political Roles (+20 points)
            'minister': 20, 'secretary': 20, 'senator': 20, 'congressman': 20, 'mp': 20,
            'governor': 20, 'political party leader': 20, 'opposition leader': 20, 'chancellor': 20,
            'cabinet': 20, 'government minister': 20, 'leader': 20,
            
            # Tier 3: Other Political (+15 points)
            'politician': 15, 'mayor': 15, 'diplomat': 15, 'ambassador': 15,
            'general': 15, 'admiral': 15, 'military': 15,
            
            # Tier 4: Business/Tech Leaders (+12 points)
            'ceo': 12, 'founder': 12, 'entrepreneur': 12, 'billionaire': 12,
            'chief executive': 12, 'businesspeople': 12, 'tech': 12,
            
            # Tier 5: Other Newsworthy (+8 points)
            'religious leader': 8, 'pope': 8, 'cardinal': 8, 'activist': 8,
            'nobel': 8, 'scientist': 8, 'journalist': 8, 'author': 8,
            
            # Negative Tier (-10 points)
            'athlete': -10, 'player': -10, 'footballer': -10, 'basketball': -10,
            'reality television': -10, 'social media': -10, 'influencer': -10,
            'youtuber': -10, 'model': -10
        }
        
        # Minimum score threshold for returning a result
        self.min_score_threshold = 0
    
    def _load_json(self, file_path: Path) -> dict:
        """Load JSON file"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Could not load {file_path}: {e}")
        return {}
    
    def _save_json(self, data: dict, file_path: Path) -> None:
        """Save JSON file with metadata"""
        try:
            output = {
                "_metadata": {
                    "last_updated": datetime.now().isoformat(),
                    "total_entries": len([k for k in data.keys() if not k.startswith('_')])
                }
            }
            
            for key in sorted([k for k in data.keys() if not k.startswith('_')], key=str.lower):
                output[key] = data[key]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Could not save {file_path}: {e}")
    
    def clean_name(self, name: str) -> str:
        """Basic name cleaning"""
        if not name:
            return ""
        
        cleaned = re.sub(r"""^["'—\-#]+|["'—\-#]+$""", '', str(name).strip())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def capitalize_name(self, name: str) -> str:
        """Capitalize the first letter of each word in a name"""
        if not name:
            return name
        
        # Split by spaces and capitalize each word
        words = name.split()
        capitalized_words = [word.capitalize() for word in words if word]
        return ' '.join(capitalized_words)
    
    def normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text by removing diacritics for better matching.
        This handles cases like 'Orban' vs 'Orbán', 'Erdogan' vs 'Erdoğan'
        """
        if not text:
            return ""
        
        # Normalize unicode and remove diacritics
        normalized = unicodedata.normalize('NFD', text)
        without_diacritics = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        return without_diacritics.lower().strip()
    
    def calculate_name_similarity_score(self, search_name: str, wikipedia_title: str) -> int:
        """Calculate similarity score between search name and Wikipedia title with diacritics normalization"""
        search_lower = search_name.lower().strip()
        title_lower = wikipedia_title.lower().strip()
        
        # Also create normalized versions for diacritics comparison
        search_normalized = self.normalize_for_comparison(search_name)
        title_normalized = self.normalize_for_comparison(wikipedia_title)
        
        # Exact match (highest priority) - check both original and normalized
        if search_lower == title_lower or search_normalized == title_normalized:
            return 50
        
        # Search name is fully contained in title - check both versions
        if (search_lower in title_lower or search_normalized in title_normalized):
            return 30
        
        # Title is contained in search name - check both versions
        if (title_lower in search_lower or title_normalized in search_normalized):
            return 25
        
        # Word-level matching for multi-word names - use normalized versions for better matching
        search_words = set(search_normalized.split())
        title_words = set(title_normalized.split())
        common_words = search_words.intersection(title_words)
        
        if common_words and len(search_words) > 0:
            # Calculate match ratio based on search terms
            match_ratio = len(common_words) / len(search_words)
            return int(match_ratio * 20)  # Up to +20 points for partial matches
        
        return 0  # No similarity
    
    def get_categories_with_retry(self, title: str, max_retries: int = 3) -> List[str]:
        """Get categories for a single title with retry mechanism"""
        
        # Check cache first
        if title in self.categories_cache:
            return self.categories_cache[title]
        
        for attempt in range(max_retries):
            try:
                categories_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    'action': 'query',
                    'format': 'json',
                    'prop': 'categories',
                    'titles': title,
                    'cllimit': 500,
                    'clshow': '!hidden'
                }
                
                response = requests.get(categories_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    pages = data.get('query', {}).get('pages', {})
                    
                    for page_id, page_data in pages.items():
                        if 'categories' in page_data:
                            categories_raw = page_data['categories']
                            category_names = [cat['title'].replace('Category:', '') for cat in categories_raw]
                            
                            # Cache the result
                            self.categories_cache[title] = category_names
                            return category_names
                        else:
                            # Page exists but no categories
                            self.categories_cache[title] = []
                            return []
                
            except Exception as e:
                logging.debug(f"Categories API attempt {attempt + 1} failed for '{title}': {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        logging.warning(f"Failed to get categories for '{title}' after {max_retries} attempts")
        self.categories_cache[title] = []
        return []
    
    def score_person_by_categories(self, categories: List[str]) -> Tuple[int, List[str]]:
        """Score a person based on their Wikipedia categories"""
        if not categories:
            return 1, ["+1(living_person)"]
        
        categories_text = ' '.join(categories).lower()
        score = 0
        reasons = []
        
        # Find the highest scoring keyword
        for keyword, points in self.scoring_keywords.items():
            if keyword in categories_text:
                score += points
                if points > 0:
                    reasons.append(f"+{points}({keyword})")
                else:
                    reasons.append(f"{points}({keyword})")
                break  # Only count the first/highest match
        
        # If no keywords found, give minimal score for being a living person
        if score == 0:
            score = 1
            reasons.append("+1(living_person)")
        
        return score, reasons
    
    def score_candidate(self, search_name: str, wikipedia_title: str, categories: List[str]) -> Tuple[int, List[str]]:
        """
        Combined scoring: name similarity + category relevance
        This is the core scoring logic that determines the best match.
        """
        total_score = 0
        reasons = []
        
        # 1. Name similarity scoring (now with diacritics normalization)
        name_score = self.calculate_name_similarity_score(search_name, wikipedia_title)
        if name_score > 0:
            total_score += name_score
            reasons.append(f"+{name_score}(name_match)")
        
        # 2. Category-based scoring (existing logic)
        category_score, category_reasons = self.score_person_by_categories(categories)
        total_score += category_score
        reasons.extend(category_reasons)
        
        return total_score, reasons
    
    def wikipedia_search_living_people(self, name: str) -> Optional[str]:
        """
        Search Wikipedia for living people and return the highest scoring match.
        This is the core logic that gets called for cache misses.
        """
        
        # Check search cache first
        search_key = f"{name.lower()} incategory:living_people"
        if search_key in self.search_cache:
            search_results = self.search_cache[search_key]
        else:
            # Perform new search
            try:
                search_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    'action': 'query',
                    'format': 'json',
                    'list': 'search',
                    'srsearch': f"{name} incategory:Living_people",
                    'srlimit': 10,  
                    'srprop': 'snippet|size'
                }
                
                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    search_results = data.get('query', {}).get('search', [])
                    
                    # Cache search results
                    self.search_cache[search_key] = search_results
                else:
                    logging.warning(f"Search failed for '{name}': HTTP {response.status_code}")
                    return None
                    
            except Exception as e:
                logging.warning(f"Search failed for '{name}': {e}")
                return None
        
        if not search_results:
            logging.debug(f"No search results for '{name}'")
            return None
        
        # Pre-filter: Only process candidates with some name similarity (now with diacritics normalization)
        relevant_candidates = []
        for result in search_results:
            title = result.get('title', '')
            name_similarity = self.calculate_name_similarity_score(name, title)
            
            # Only process candidates with at least some name similarity
            if name_similarity > 0:
                relevant_candidates.append(result)
        
        if not relevant_candidates:
            logging.debug(f"No relevant candidates found for '{name}' after name similarity filtering")
            return None
        
        # Score all relevant candidates
        candidates = []
        for result in relevant_candidates:
            title = result.get('title', '')
            
            # Get categories for this person
            categories = self.get_categories_with_retry(title)
            
            # Combined scoring: name similarity + categories
            total_score, reasons = self.score_candidate(name, title, categories)
            
            candidates.append({
                'title': title,
                'score': total_score,
                'reasons': reasons,
                'categories_count': len(categories)
            })
        
        # Sort by score and return the highest scorer
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        if candidates:
            best = candidates[0]
            
            # Only return if score meets minimum threshold
            if best['score'] >= self.min_score_threshold:
                reasons_str = ', '.join(best['reasons'][:4])  # Show more reasons
                
                logging.info(f"Wikipedia: '{name}' -> '{best['title']}' "
                           f"(score: {best['score']}, categories: {best['categories_count']}, "
                           f"reasons: {reasons_str})")
                
                return best['title']
            else:
                logging.debug(f"Best candidate for '{name}' scored {best['score']} < {self.min_score_threshold} threshold")
        
        return None
    
    def resolve_person_name(self, name: str) -> str:
        """
        Main resolution method using cache-first approach.
        This is where the 90%+ cache hit magic happens.
        """
        cleaned_name = self.clean_name(name)
        if not cleaned_name or len(cleaned_name) < 2:
            return self.capitalize_name(name)
        
        cache_key = cleaned_name.lower()
        
        # Step 1: Check cache first (will be 90%+ hit rate after initial runs)
        if cache_key in self.person_cache:
            cached_result = self.person_cache[cache_key]
            if cached_result:  # Don't return empty strings
                return cached_result
            else:
                return self.capitalize_name(name)  # Was searched but no good match found
        
        # Step 2: Cache miss - do full Wikipedia search (rare after initial runs)
        logging.info(f"Cache miss for '{name}' - performing Wikipedia search")
        result = self.wikipedia_search_living_people(name)
        
        # Step 3: Cache the result (even if None)
        self.person_cache[cache_key] = result
        
        # Return the result or capitalized original name if no match
        return result if result else self.capitalize_name(name)
    
    def simple_deduplicate(self, names: List[str]) -> List[str]:
        """Group names by lowercase, pick best from each group"""
        if not names:
            return []
        
        groups = {}
        for name in names:
            cleaned = self.clean_name(name)
            if len(cleaned) < 2 or any(char.isdigit() for char in cleaned):
                continue
                
            key = cleaned.lower()
            if key not in groups:
                groups[key] = []
            groups[key].append(cleaned)
        
        result = []
        for group in groups.values():
            best = max(group, key=lambda x: (x.istitle(), len(x)))
            result.append(best)
        
        return result
    
    def resolve_entities(self, names: List[str]) -> List[str]:
        """Process a list of person names"""
        if not names:
            return []
        
        # Step 1: Deduplicate input names
        deduplicated = self.simple_deduplicate(names)
        
        # Step 2: Resolve each name (cache-first approach)
        resolved = []
        for name in deduplicated:
            result = self.resolve_person_name(name)
            # Include all resolved names (whether they changed or not)
            if result:  # Only exclude empty/None results
                resolved.append(result)
        
        # Step 3: Final deduplication
        return list(dict.fromkeys(resolved))
    
    def save_caches(self) -> None:
        """Save all caches"""
        self._save_json(self.person_cache, self.person_cache_file)
        self._save_json(self.search_cache, self.search_cache_file)
        self._save_json(self.categories_cache, self.categories_cache_file)
        logging.info("Saved all caches")
    
    def update_persons_mentioned(self, posts: List[Dict]) -> List[Dict]:
        """Main pipeline interface"""
        cache_misses = 0
        initial_cache_size = len([k for k in self.person_cache.keys() if not k.startswith('_')])
        
        print("Processing person names using cached Wikipedia mappings...")
        
        for i, post in enumerate(posts):
            persons = post.get("persons_mentioned", [])
            if persons:
                try:
                    resolved = self.resolve_entities(persons)
                    post["persons_mentioned_updated"] = resolved
                    
                    # Log transformations
                    if resolved:
                        print(f"Post {i+1}: {persons} -> {resolved}")
                        
                except Exception as e:
                    print(f"Error processing persons for post {i+1}: {e}")
                    post["persons_mentioned_updated"] = []
            else:
                post["persons_mentioned_updated"] = []
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(posts)} posts")
        
        # Count cache misses and save if there were new lookups
        current_cache_size = len([k for k in self.person_cache.keys() if not k.startswith('_')])
        cache_misses = current_cache_size - initial_cache_size
        
        if cache_misses > 0:
            self.save_caches()
            logging.info(f"Had {cache_misses} cache misses - performed new Wikipedia lookups")
        else:
            logging.info("All names resolved from cache - no Wikipedia API calls needed!")
        
        return posts
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        return {
            "person_mappings": len([k for k in self.person_cache.keys() if not k.startswith('_')]),
            "search_cache": len([k for k in self.search_cache.keys() if not k.startswith('_')]),
            "categories_cache": len([k for k in self.categories_cache.keys() if not k.startswith('_')])
        }
    
    def add_manual_mapping(self, input_name: str, correct_name: str) -> None:
        """Add manual mapping to cache"""
        self.person_cache[input_name.lower()] = correct_name
        logging.info(f"Added manual mapping: '{input_name}' -> '{correct_name}'")
    
    def debug_search_results(self, name: str) -> None:
        """Debug method to see what candidates are found and their scores"""
        print(f"\n=== DEBUG: Search results for '{name}' ===")
        
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': f"{name} incategory:Living_people",
            'srlimit': 10,
            'srprop': 'snippet|size'
        }
        
        try:
            response = requests.get(search_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('query', {}).get('search', [])
                
                print(f"Found {len(search_results)} search results:")
                
                for i, result in enumerate(search_results):
                    title = result.get('title', '')
                    categories = self.get_categories_with_retry(title)
                    score, reasons = self.score_candidate(name, title, categories)
                    
                    print(f"\n{i+1}. {title}")
                    print(f"   Score: {score}")
                    print(f"   Reasons: {', '.join(reasons)}")
                    print(f"   Categories: {len(categories)}")
                    
        except Exception as e:
            print(f"Debug failed: {e}")