import logging
from typing import List, Dict, Tuple, Optional

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

    def __init__(self, user_agent="reddit_worldnews_pipeline"):
        """
        Initializes the LocationProcessor with geocoding tools and direct mappings.
        """
        self.geolocator = Nominatim(user_agent=user_agent)
        self.geocode = RateLimiter(self.geolocator.geocode, min_delay_seconds=1.0, max_retries=1)
        
        # Cache for location lookups to avoid repeated geocoding
        self.location_cache = {}
        self.region_cache = {}

        self.middle_east_countries = {
            'Israel', 'Palestine, State of', 'Iran, Islamic Republic of', 'Iraq', 
            'Saudi Arabia', 'Yemen', 'Syrian Arab Republic', 'Jordan', 'Lebanon', 
            'United Arab Emirates', 'Qatar', 'Kuwait', 'Bahrain', 'Oman',
            'Turkey', 'Afghanistan', 'Cyprus'
        }
        
        
        self.direct_mappings = {
            # Standard abbreviations
            'US': ('United States', 'US'),
            'UK': ('United Kingdom', 'GB'),
            'USA': ('United States', 'US'),
            'UAE': ('United Arab Emirates', 'AE'),
            'PRC': ('China', 'CN'),
            
            # Regional/Political designations
            'ROC': ('Taiwan, Province of China', 'TW'),
            'DR': ('Dominican Republic', 'DO'),
            'N Korea': ("Korea, Democratic People's Republic of", 'KP'),
            'S Korea': ('Korea, Republic of', 'KR'),
            'Korea': ('Korea, Republic of', 'KR'),
            
            # Alternative country names
            'Britain': ('United Kingdom', 'GB'),
            'England': ('United Kingdom', 'GB'),
            'Scotland': ('United Kingdom', 'GB'),
            'America': ('United States', 'US'),
            
            # Major cities mapped to countries
            'Kyiv': ('Ukraine', 'UA'),
            'Moscow': ('Russian Federation', 'RU'),
            'Kremlin': ('Russian Federation', 'RU'),
            'Beijing': ('China', 'CN'),
            'Istanbul': ('Turkey', 'TR'),
            'Rome': ('Italy', 'IT'),
            'Washington': ('United States', 'US'),
            'Berlin': ('Germany', 'DE'),
            'Vancouver': ('Canada', 'CA'),
            'White House': ('United States', 'US'),
            'Geneva': ('Switzerland', 'CH'),
            'London': ('United Kingdom', 'GB'),
            'Paris': ('France', 'FR'),
            'Brussels': ('Belgium', 'BE'),
            'Tehran': ('Iran, Islamic Republic of', 'IR'),
            'Warsaw': ('Poland', 'PL'),
            'Damascus': ('Syrian Arab Republic', 'SY'),
            'Mexico City': ('Mexico', 'MX'),
            'New York': ('United States', 'US'),
            'New Delhi': ('India', 'IN'),
            'Mumbai': ('India', 'IN'),
            'Lahore': ('Pakistan', 'PK'),
            'Jerusalem': ('Israel', 'IL'),
            'Tel Aviv': ('Israel', 'IL'),
            
            # Regions/Territories
            'Hong Kong': ('China', 'CN'),
            'Vatican': ('Holy See (Vatican City State)', 'VA'),
            'Alberta': ('Canada', 'CA'),
            'Ontario': ('Canada', 'CA'),
            'Kursk': ('Russian Federation', 'RU'),
            'Kursk Oblast': ('Russian Federation', 'RU'),
            'Crimea': ('Ukraine', 'UA'),
            
            # Disputed/Special territories
            'Gaza': ('Palestine, State of', 'PS'),
            'West Bank': ('Palestine, State of', 'PS'),
            'Kashmir': ('India', 'IN'),
            'LoC': ('India', 'IN'),  # Line of Control
            'Jammu': ('India', 'IN'),
            
            # Geographic features
            'South China Sea': ('China', 'CN'),
        }

    def get_country_info(self, location: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Gets the country name and ISO code for a given location.
        Uses caching to avoid repeated lookups.

        Args:
            location (str): The location string to geocode.

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the country name and ISO code,
                                                both of which can be None if not found.
        """
        if not location:
            return None, None

        location = location.strip()
        
        # Check cache first
        if location in self.location_cache:
            return self.location_cache[location]

        # 1. Check direct mappings (fastest)
        if location in self.direct_mappings:
            country_name, iso_code = self.direct_mappings[location]
            self.location_cache[location] = (country_name, iso_code)
            return country_name, iso_code

        # 2. Check if it's already a country name
        try:
            country = pycountry.countries.search_fuzzy(location)[0]
            result = (country.name, country.alpha_2)
            self.location_cache[location] = result
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
                                self.location_cache[location] = result
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
        self.location_cache[location] = (None, None)
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
            
        # Check cache first
        cache_key = iso_code or country_name
        if cache_key in self.region_cache:
            return self.region_cache[cache_key]
        
        continent = None
        
        # Try pycountry_convert first if available
        if iso_code:
            try:
                continent_code = pc.country_alpha2_to_continent_code(iso_code)
                continent = pc.convert_continent_code_to_continent_name(continent_code)
                
                # Replace Asia with Middle East for Middle East countries
                if continent == 'Asia' and country_name in self.middle_east_countries:
                    continent = 'Middle East'

            except Exception as e:
                logging.debug(f"pycountry_convert failed for {country_name} ({iso_code}): {e}")
        
        # Cache the result
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

        Args:
            posts (List[Dict]): A list of post dictionaries.

        Returns:
            List[Dict]: A list of post dictionaries with added location information.
        """
        processed_posts = []
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
                
        return processed_posts