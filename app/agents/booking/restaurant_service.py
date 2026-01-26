"""Restaurant service with Redis caching and fuzzy matching."""
from typing import List, Optional
from app.agents.booking.models import Restaurant
from app.agents.booking.api_client import api_client
from app.config import settings
import json
import logging
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class RestaurantService:
    """Service for managing restaurant data with caching."""
    
    def __init__(self):
        """Initialize restaurant service."""
        self.redis_client = None
        self.use_redis = False
        self.local_cache: List[Restaurant] = []
        self.cache_key = "restaurants:all"
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection if available."""
        if settings.environment == "production":
            try:
                import redis.asyncio as aioredis
                self.redis_client = aioredis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password if settings.redis_password else None,
                    decode_responses=True
                )
                self.use_redis = True
                logger.info("Restaurant service using Redis cache")
            except Exception as e:
                logger.warning(f"Redis not available for restaurant cache: {e}")
                self.use_redis = False
        else:
            logger.info("Restaurant service using in-memory cache (development mode)")
            self.use_redis = False
    
    async def prefetch_restaurants(self) -> List[Restaurant]:
        """
        Fetch all restaurants from API and cache them.
        Called on application startup.
        
        Returns:
            List of Restaurant objects
        """
        try:
            logger.info("Prefetching restaurants from API...")
            
            # Fetch from API
            restaurants_data = await api_client.fetch_restaurants()
            restaurants = [Restaurant(**r) for r in restaurants_data]
            
            # Cache the results
            if self.use_redis:
                await self._cache_to_redis(restaurants)
            else:
                self.local_cache = restaurants
            
            logger.info(f"Successfully cached {len(restaurants)} restaurants")
            return restaurants
            
        except Exception as e:
            logger.error(f"Error prefetching restaurants: {e}")
            # Return empty list on error, don't crash the app
            return []
    
    async def _cache_to_redis(self, restaurants: List[Restaurant]):
        """Cache restaurants to Redis."""
        try:
            restaurants_json = json.dumps([r.model_dump() for r in restaurants])
            await self.redis_client.setex(
                self.cache_key,
                3600,  # 1 hour TTL
                restaurants_json
            )
            logger.info("Restaurants cached to Redis")
        except Exception as e:
            logger.error(f"Error caching to Redis: {e}")
    
    async def get_all_restaurants(self) -> List[Restaurant]:
        """
        Get all restaurants from cache.
        
        Returns:
            List of Restaurant objects
        """
        try:
            if self.use_redis:
                # Try to get from Redis
                cached = await self.redis_client.get(self.cache_key)
                if cached:
                    restaurants_data = json.loads(cached)
                    return [Restaurant(**r) for r in restaurants_data]
                else:
                    # Cache expired, refetch
                    logger.info("Cache expired, refetching restaurants")
                    return await self.prefetch_restaurants()
            else:
                # Use local cache
                if not self.local_cache:
                    # Cache not initialized, fetch now
                    return await self.prefetch_restaurants()
                return self.local_cache
                
        except Exception as e:
            logger.error(f"Error getting restaurants: {e}")
            return []
    
    async def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Restaurant]:
        """
        Get a specific restaurant by ID.
        
        Args:
            restaurant_id: Restaurant ID
            
        Returns:
            Restaurant object or None
        """
        restaurants = await self.get_all_restaurants()
        for restaurant in restaurants:
            if restaurant.id == restaurant_id:
                return restaurant
        return None
    
    async def find_restaurant_by_name(
        self,
        name: str,
        threshold: float = 75.0
    ) -> Optional[Restaurant]:
        """
        Find restaurant by name using fuzzy matching.
        
        Args:
            name: Restaurant name to search for
            threshold: Minimum similarity score (0-100)
            
        Returns:
            Best matching Restaurant or None
        """
        restaurants = await self.get_all_restaurants()
        if not restaurants:
            return None
        
        # Create list of restaurant names
        restaurant_names = {r.name: r for r in restaurants}
        
        # Use fuzzy matching to find best match
        result = process.extractOne(
            name,
            restaurant_names.keys(),
            scorer=fuzz.ratio
        )
        
        if result and result[1] >= threshold:
            matched_name = result[0]
            score = result[1]
            logger.info(f"Fuzzy match: '{name}' -> '{matched_name}' (score: {score})")
            return restaurant_names[matched_name]
        
        logger.info(f"No fuzzy match found for '{name}' (threshold: {threshold})")
        return None
    
    async def find_similar_restaurants(
        self,
        name: str,
        limit: int = 3,
        threshold: float = 60.0
    ) -> List[tuple[Restaurant, float]]:
        """
        Find multiple similar restaurants by name.
        Useful when exact match is unclear.
        
        Args:
            name: Restaurant name to search for
            limit: Maximum number of results
            threshold: Minimum similarity score (0-100)
            
        Returns:
            List of (Restaurant, score) tuples
        """
        restaurants = await self.get_all_restaurants()
        if not restaurants:
            return []
        
        # Create list of restaurant names
        restaurant_names = {r.name: r for r in restaurants}
        
        # Get top matches
        results = process.extract(
            name,
            restaurant_names.keys(),
            scorer=fuzz.ratio,
            limit=limit
        )
        
        # Filter by threshold and convert to Restaurant objects
        matches = []
        for matched_name, score, _ in results:
            if score >= threshold:
                matches.append((restaurant_names[matched_name], score))
        
        logger.info(f"Found {len(matches)} similar restaurants for '{name}'")
        return matches
    
    async def search_restaurants(
        self,
        cuisine: Optional[str] = None,
        location: Optional[str] = None,
        min_rating: Optional[float] = None,
        price_range: Optional[str] = None
    ) -> List[Restaurant]:
        """
        Search restaurants with filters.
        
        Args:
            cuisine: Filter by cuisine type
            location: Filter by location (fuzzy match)
            min_rating: Minimum rating
            price_range: Price range filter
            
        Returns:
            List of matching restaurants
        """
        restaurants = await self.get_all_restaurants()
        
        # Apply filters
        filtered = restaurants
        
        if cuisine:
            filtered = [r for r in filtered if cuisine.lower() in r.cuisine.lower()]
        
        if location:
            filtered = [r for r in filtered if location.lower() in r.location.lower()]
        
        if min_rating is not None:
            filtered = [r for r in filtered if r.rating and r.rating >= min_rating]
        
        if price_range:
            filtered = [r for r in filtered if r.price_range == price_range]
        
        logger.info(f"Search returned {len(filtered)} restaurants")
        return filtered


# Global instance
restaurant_service = RestaurantService()
