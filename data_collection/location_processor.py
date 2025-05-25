import logging
from typing import List, Dict, Tuple, Optional

# Import geocoding libraries
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import reverse_geocoder as rg
import pycountry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class LocationProcessor:
    """
    A class to process locations mentioned in Reddit posts,
    geocoding them to obtain country names and ISO codes.
    """

    def __init__(self, user_agent="reddit_worldnews_pipeline"):
        """
        Initializes the LocationProcessor with geocoding tools and direct mappings.
        """
        self.geolocator = Nominatim(user_agent=user_agent)
        self.geocode = RateLimiter(self.geolocator.geocode, min_delay_seconds=1.0, max_retries=1)
        self.direct_mappings = {
            'US': ('United States', 'US'),
            'U': ('United States', 'US'),
            'S': ('United States', 'US'),
            'S.': ('United States', 'US'),
            'K': ('United Kingdom', 'GB'),
            'UK': ('United Kingdom', 'GB'),
            'UAE': ('United Arab Emirates', 'AE'),
            'ROC': ('Taiwan, Province of China', 'TW'),
            'DR': ('Dominican Republic', 'DO'),
            'N Korea': ("Korea, Democratic People's Republic of", 'KP'),
            'S Korea': ('Korea, Republic of', 'KR'),
            'Korea': ('Korea, Republic of', 'KR'),
            'S. Korea': ('Korea, Republic of', 'KR'),
            'SA': ('Saudi Arabia', 'SA'),
            'PRC': ('China', 'CN'),
            'USA': ('United States', 'US'),
            'U.S.': ('United States', 'US'),
            'U.K.': ('United Kingdom', 'GB'),
            'Kyiv': ('Ukraine', 'UA'),
            'LoC': ('India', 'IN'),
            'Gaza': ('Palestine, State of', 'PS'),
            'West Bank': ('Palestine, State of', 'PS'),
            'Kashmir': ('India', 'IN'),
            'Moscow': ('Russian Federation', 'RU'),
            'Kremlin': ('Russian Federation', 'RU'),
            'Beijing': ('China', 'CN'),
            'Britain': ('United Kingdom', 'GB'),
            'England': ('United Kingdom', 'GB'),
            'Scotland': ('United Kingdom', 'GB'),
            'Istanbul': ('Turkey', 'TR'),
            'Vatican': ('Holy See (Vatican City State)', 'VA'),
            'Kursk': ('Russian Federation', 'RU'),
            'Alberta': ('Canada', 'CA'),
            'Crimea': ('Ukraine', 'UA'),
            'Rome': ('Italy', 'IT'),
            'Washington': ('United States', 'US'),
            'Berlin': ('Germany', 'DE'),
            'South China Sea': ('China', 'CN'),
            'Vancouver': ('Canada', 'CA'),
            'White House': ('United States', 'US'),
            'Geneva': ('Switzerland', 'CH'),
            'London': ('United Kingdom', 'GB'),
            'Paris': ('France', 'FR'),
            'Brussels': ('Belgium', 'BE'),
            'Tehran': ('Iran, Islamic Republic of', 'IR'),
            'Warsaw': ('Poland', 'PL'),
            'Damascus': ('Syrian Arab Republic', 'SY'),
            'Hong Kong': ('China', 'CN'),
            'Kursk Oblast': ('Russian Federation', 'RU'),
            'Mexico City': ('Mexico', 'MX'),
            'Ontario': ('Canada', 'CA'),
            'America': ('United States', 'US'),
            'New York': ('United States', 'US'),
            'Jammu': ('India', 'IN'),
            'New Delhi': ('India', 'IN'),
            'Mumbai': ('India', 'IN'),
            'Lahore': ('Pakistan', 'PK'),
            'Jerusalem': ('Israel', 'IL'),
            'Tel Aviv': ('Israel', 'IL')
        }

    def get_country_info(self, location: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Gets the country name and ISO code for a given location.

        Args:
            location (str): The location string to geocode.

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the country name and ISO code,
                                                both of which can be None if not found.
        """
        if not location:
            return None, None

        location = location.strip()

        # 1. Check direct mappings (fastest)
        if location in self.direct_mappings:
            country_name, iso_code = self.direct_mappings[location]
            return country_name, iso_code

        # 2. Check if it's already a country name
        try:
            country = pycountry.countries.search_fuzzy(location)[0]
            return country.name, country.alpha_2
        except:
            pass

        # 3. Use geocoding
        try:
            result = self.geocode(location, exactly_one=True, language='en')
            if result and hasattr(result, 'raw') and result.raw.get('lat') and result.raw.get('lon'):
                lat, lon = float(result.raw['lat']), float(result.raw['lon'])

                # Get country from coordinates
                results = rg.search((lat, lon))
                if results and len(results) > 0:
                    country_code = results[0].get('cc')
                    if country_code:
                        try:
                            country_obj = pycountry.countries.get(alpha_2=country_code)
                            if country_obj:
                                return country_obj.name, country_obj.alpha_2
                        except:
                            pass
        except GeocoderTimedOut:
            logging.info(f"Timeout geocoding {location}, retrying...")
            return self.get_country_info(location)
        except GeocoderServiceError as e:
            logging.error(f"Geocoding service error for {location}: {e}")
            return None, None
        except Exception as e:
            logging.error(f"Error geocoding {location}: {e}")
            return None, None

        return None, None

    def process_locations(self, locations: List[str]) -> Tuple[List[str], List[str]]:
        """
        Processes a list of locations to update names and ISO codes.

        Args:
            locations (List[str]): A list of location strings.

        Returns:
            Tuple[List[str], List[str]]: A tuple containing lists of updated location names and ISO codes.
        """
        updated_names = []
        iso_codes = []

        for location in locations:
            if isinstance(location, str):
                try:
                    result = self.get_country_info(location)
                    if isinstance(result, tuple) and len(result) == 2:
                        country_name, iso_code = result
                        updated_names.append(country_name if country_name else location)
                        iso_codes.append(iso_code if iso_code else None)
                    else:
                        # Fallback if function doesn't return expected tuple
                        updated_names.append(location)
                        iso_codes.append(None)
                except Exception as e:
                    logging.error(f"Error processing location '{location}': {e}")
                    updated_names.append(location)
                    iso_codes.append(None)
            else:
                updated_names.append(location)
                iso_codes.append(None)

        return updated_names, iso_codes

    def process_posts(self, posts: List[Dict]) -> List[Dict]:
        """
        Processes a list of posts to add updated location information.

        Args:
            posts (List[Dict]): A list of post dictionaries.

        Returns:
            List[Dict]: A list of post dictionaries with added location information.
        """
        processed_posts = []
        for post in posts:
            try:
                locations = post.get('locations_mentioned', [])
                if isinstance(locations, list):
                    updated_names, iso_codes = self.process_locations(locations)
                    post['locations_mentioned_updated'] = updated_names
                    post['locations_mentioned_iso_code'] = iso_codes
                else:
                    post['locations_mentioned_updated'] = []
                    post['locations_mentioned_iso_code'] = []
                processed_posts.append(post)
            except Exception as e:
                logging.error(f"Error processing post: {e}")
                processed_posts.append(post)  # Append original post even if there's an error
        return processed_posts