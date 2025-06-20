import logging
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime

# Import geocoding libraries
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import reverse_geocoder as rg
import pycountry
import pycountry_convert as pc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LocationProcessor:
    """
    A class to process locations mentioned in Reddit posts,
    geocoding them to obtain country names and ISO codes, and mapping to regions.
    """

    def __init__(self, user_agent="reddit_worldnews_pipeline", cache_dir="data"):
        """
        Initializes the LocationProcessor with geocoding tools and persistent caching.
        """
        self.geolocator = Nominatim(user_agent=user_agent)
        self.geocode = RateLimiter(self.geolocator.geocode, min_delay_seconds=1.0, max_retries=1)
        
        # Setup cache files
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.location_cache_file = self.cache_dir / "location_cache.json"
        self.region_cache_file = self.cache_dir / "region_cache.json"
        
        # Load existing caches or initialize empty ones
        self.location_cache = self._load_cache(self.location_cache_file)
        self.region_cache = self._load_cache(self.region_cache_file)
        
        print(f"Loaded {len(self.location_cache)} location mappings from cache")
        print(f"Loaded {len(self.region_cache)} region mappings from cache")

        self.middle_east_countries = {
            'Israel', 'Palestine, State of', 'Iran, Islamic Republic of', 'Iraq', 
            'Saudi Arabia', 'Yemen', 'Syrian Arab Republic', 'Jordan', 'Lebanon', 
            'United Arab Emirates', 'Qatar', 'Kuwait', 'Bahrain', 'Oman',
            'Turkey', 'Afghanistan', 'Cyprus'
        }

    def _load_cache(self, cache_file: Path) -> dict:
        """Load cache from JSON file, return empty dict if file doesn't exist"""
        try:
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.warning(f"Could not load cache from {cache_file}: {e}")
        return {}
    
    def _save_cache_sorted(self, cache_data: dict, cache_file: Path, add_metadata: bool = True) -> None:
        """Save cache to JSON file with sorted keys and metadata"""
        try:
            output_data = {}
            
            # Add metadata header for better readability
            if add_metadata:
                output_data["_metadata"] = {
                    "last_updated": datetime.now().isoformat(),
                    "total_entries": len([k for k in cache_data.keys() if not k.startswith('_')]),
                    "description": self._get_cache_description(cache_file.name)
                }
            
            # Add sorted data (excluding metadata keys)
            data_keys = [k for k in cache_data.keys() if not k.startswith('_')]
            for key in sorted(data_keys, key=str.lower):
                output_data[key] = cache_data[key]
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logging.error(f"Could not save cache to {cache_file}: {e}")
    
    def _get_cache_description(self, filename: str) -> str:
        """Get description for cache metadata"""
        descriptions = {
            "location_cache.json": "Maps location names to [country_name, iso_code]. Automatically generated from geocoding.",
            "region_cache.json": "Maps 'ISO - Country Name' to geopolitical regions. Format: 'US - United States': 'North America'"
        }
        return descriptions.get(filename, "Cache file")
    
    def save_caches(self, name: str = None) -> None:
        """
        Save specified cache(s) to disk with sorting and metadata.
        Args:
            name (str, optional): 'location', 'region', or None to save both.
        """
        if name == "location":
            self._save_cache_sorted(self.location_cache, self.location_cache_file)
            logging.info(f"Saved {len([k for k in self.location_cache.keys() if not k.startswith('_')])} location mappings to cache")
        elif name == "region":
            self._save_cache_sorted(self.region_cache, self.region_cache_file)
            logging.info(f"Saved {len([k for k in self.region_cache.keys() if not k.startswith('_')])} region mappings to cache")
        

    def get_country_info(self, location: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Gets the country name and ISO code for a given location.
        Uses cache, then geocoding.

        Args:
            location (str): The location string to geocode.

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the country name and ISO code,
                                                both of which can be None if not found.
        """
        if not location:
            return None, None

        location = location.strip()
        
        # 1. Check cache
        if location in self.location_cache:
            cached_result = self.location_cache[location]
            if isinstance(cached_result, list) and len(cached_result) == 2:
                return tuple(cached_result)
            elif isinstance(cached_result, tuple) and len(cached_result) == 2:
                return cached_result

        # 2. Check if it's already a country name
        try:
            country = pycountry.countries.search_fuzzy(location)[0]
            result = (country.name, country.alpha_2)
            self.location_cache[location] = [result[0], result[1]]
            return result
        except:
            pass

        # 3. Use geocoding
        try:
            geocode_result = self.geocode(location, exactly_one=True, language='en')
            if geocode_result and hasattr(geocode_result, 'raw') and geocode_result.raw.get('lat') and geocode_result.raw.get('lon'):
                lat, lon = float(geocode_result.raw['lat']), float(geocode_result.raw['lon'])

                # Get country from coordinates
                results = rg.search((lat, lon))
                if results and len(results) > 0:
                    country_code = results[0].get('cc')
                    if country_code:
                        try:
                            country_obj = pycountry.countries.get(alpha_2=country_code)
                            if country_obj:
                                result = (country_obj.name, country_obj.alpha_2)
                                self.location_cache[location] = [result[0], result[1]]
                                return result
                        except:
                            pass
        except GeocoderTimedOut:
            logging.info(f"Timeout geocoding {location}, retrying...")
            return self.get_country_info(location)
        except GeocoderServiceError as e:
            logging.error(f"Geocoding service error for {location}: {e}")
        except Exception as e:
            logging.error(f"Error geocoding {location}: {e}")

        # Cache the failure to avoid repeated attempts
        self.location_cache[location] = [None, None]
        return None, None

    def get_continent_from_country(self, country_name: str, iso_code: str = None) -> Optional[str]:
        """
        Get continent/region for a country using pycountry_convert or fallback mapping.
        
        Args:
            country_name (str): Standard country name
            iso_code (str): ISO alpha-2 country code (optional)
            
        Returns:
            Optional[str]: Continent/region name
        """
        if not country_name:
            return None
            
        # Create human-readable cache key: "US - United States" or just country name if no ISO
        if iso_code:
            cache_key = f"{iso_code} - {country_name}"
        else:
            cache_key = country_name
            
        # Check cache first
        if cache_key in self.region_cache:
            return self.region_cache[cache_key]
        
        continent = None
        
        if iso_code:
            try:
                continent_code = pc.country_alpha2_to_continent_code(iso_code)
                continent = pc.convert_continent_code_to_continent_name(continent_code)
                
                # Replace Asia with Middle East for Middle East countries
                if continent == 'Asia' and country_name in self.middle_east_countries:
                    continent = 'Middle East'

            except Exception as e:
                logging.debug(f"pycountry_convert failed for {country_name} ({iso_code}): {e}")
        
        # Cache the result with readable key
        self.region_cache[cache_key] = continent
        return continent

    def process_locations(self, locations: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """
        Processes a list of locations to get updated names, ISO codes, and regions.
        Ensures deduplication of countries.

        Args:
            locations (List[str]): A list of location strings.

        Returns:
            Tuple[List[str], List[str], List[str]]: Updated country names, ISO codes, and regions.
        """
        if not locations:
            return [], [], []
        
        # Use dict to maintain order while deduplicating
        country_info = {}  # country_name -> (iso_code, region)
        
        for location in locations:
            if not isinstance(location, str) or not location.strip():
                continue
                
            try:
                country_name, iso_code = self.get_country_info(location)
                
                if country_name:
                    # Get region for this country
                    region = self.get_continent_from_country(country_name, iso_code)
                    
                    # Store in dict (automatically deduplicates)
                    country_info[country_name] = (iso_code, region)
                    
            except Exception as e:
                logging.error(f"Error processing location '{location}': {e}")
        
        # Extract deduplicated lists
        updated_names = list(country_info.keys())
        iso_codes = [info[0] for info in country_info.values()]
        regions = [info[1] for info in country_info.values() if info[1]]
        
        # Deduplicate regions as well
        unique_regions = list(dict.fromkeys(regions))  # Preserves order
        
        return updated_names, iso_codes, unique_regions

    def process_posts(self, posts: List[Dict]) -> List[Dict]:
        """
        Processes a list of posts to add updated location information and regions.
        Automatically saves cache after processing.

        Args:
            posts (List[Dict]): A list of post dictionaries.

        Returns:
            List[Dict]: A list of post dictionaries with added location information.
        """
        processed_posts = []
        initial_location_cache_size = len([k for k in self.location_cache.keys() if not k.startswith('_')])
        initial_region_cache_size = len([k for k in self.region_cache.keys() if not k.startswith('_')])

        for post in posts:
            try:
                locations = post.get('locations_mentioned', [])               
                if isinstance(locations, list) and locations:
                    updated_names, iso_codes, regions = self.process_locations(locations)
                    post['locations_mentioned_updated'] = updated_names
                    post['locations_mentioned_iso_code'] = iso_codes
                    post['regions_mentioned'] = regions
                else:
                    post['locations_mentioned_updated'] = []
                    post['locations_mentioned_iso_code'] = []
                    post['regions_mentioned'] = []
                    
                processed_posts.append(post)                
            except Exception as e:
                logging.error(f"Error processing post: {e}")
                # Add empty fields and continue
                post['locations_mentioned_updated'] = []
                post['locations_mentioned_iso_code'] = []
                post['regions_mentioned'] = []
                processed_posts.append(post)
        
        # Save cache if we added new entries
        current_location_cache_size = len([k for k in self.location_cache.keys() if not k.startswith('_')])
        current_region_cache_size = len([k for k in self.region_cache.keys() if not k.startswith('_')])

        location_cache_updates = current_location_cache_size - initial_location_cache_size
        region_cache_updates = current_region_cache_size - initial_region_cache_size
        
        if location_cache_updates > 0:
            self.save_caches("location")
            logging.info(f"Added {location_cache_updates} new location mappings to cache")
        if region_cache_updates > 0:
            self.save_caches("region")
            logging.info(f"Added {region_cache_updates} new region mappings to cache")
        
        return processed_posts