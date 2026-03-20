"""
Async Hacker News API client using Firebase API and Algolia.
Supports parallel fetching with semaphore limiting and exponential backoff.
"""
import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# API base URLs
BASE_URL_FIREBASE = "https://hacker-news.firebaseio.com/v0"
BASE_URL_ALGOLIA = "https://hn.algolia.com/api/v1"


class HNBaseError(Exception):
    """Base exception for HN client errors."""
    pass


class HNRateLimitError(HNBaseError):
    """Raised when HN API rate limits are exceeded."""
    pass


class HNClient:
    """
    Async Hacker News API client.
    
    Uses Firebase API for HN items and Algolia for search and comment threads.
    Implements parallel fetching with semaphore limiting and exponential backoff.
    """
    
    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        """
        Initialize HN client.
        
        Args:
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts for failed requests.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "HNClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            follow_redirects=True,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                follow_redirects=True,
            )
        return self._client
    
    async def _request_with_retry(
        self, 
        url: str, 
        retries: int = 0
    ) -> dict[str, Any] | list | None:
        """
        Make HTTP request with exponential backoff on failure.
        
        Args:
            url: URL to request.
            retries: Current retry count.
            
        Returns:
            JSON response data or None on failure.
        """
        client = await self._get_client()
        
        try:
            response = await client.get(url)
            
            if response.status_code == 429:
                if retries < self.max_retries:
                    wait_time = (0.5 * (2 ** retries)) + (asyncio.get_event_loop().time() % 1)
                    logger.warning(f"Rate limited. Retrying in {wait_time:.1f}s (attempt {retries + 1})")
                    await asyncio.sleep(wait_time)
                    return await self._request_with_retry(url, retries + 1)
                raise HNRateLimitError("Max retries exceeded for rate limit")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if retries < self.max_retries:
                wait_time = (0.5 * (2 ** retries)) + (asyncio.get_event_loop().time() % 1)
                logger.warning(f"Request failed: {e}. Retrying in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                return await self._request_with_retry(url, retries + 1)
            logger.error(f"Request failed after {self.max_retries} retries: {e}")
            raise HNBaseError(f"Request failed: {e}") from e
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise HNBaseError(f"Request error: {e}") from e
    
    async def fetch_item(self, item_id: int) -> dict[str, Any] | None:
        """
        Fetch a single HN item from Firebase API.
        
        Args:
            item_id: HN item ID.
            
        Returns:
            Item data dict or None if not found.
        """
        url = f"{BASE_URL_FIREBASE}/item/{item_id}.json"
        logger.info(f"Fetching HN item {item_id}")
        
        data = await self._request_with_retry(url)
        
        if data is None:
            logger.warning(f"Item {item_id} not found or deleted")
            
        return data
    
    async def fetch_items_batch(
        self, 
        item_ids: list[int], 
        semaphore: int = 5
    ) -> list[dict[str, Any]]:
        """
        Fetch multiple HN items in parallel using asyncio.gather.
        
        Args:
            item_ids: List of HN item IDs to fetch.
            semaphore: Maximum concurrent requests.
            
        Returns:
            List of successfully fetched item dicts.
        """
        sem = asyncio.Semaphore(semaphore)
        
        async def fetch_with_sem(item_id: int) -> dict[str, Any] | None:
            async with sem:
                try:
                    return await self.fetch_item(item_id)
                except HNBaseError:
                    return None
        
        logger.info(f"Fetching {len(item_ids)} items with semaphore={semaphore}")
        results = await asyncio.gather(*[fetch_with_sem(id) for id in item_ids], return_exceptions=True)
        
        # Filter out None and exceptions
        valid_items = [r for r in results if r is not None and not isinstance(r, Exception)]
        
        logger.info(f"Successfully fetched {len(valid_items)}/{len(item_ids)} items")
        return valid_items
    
    async def fetch_story_ids(self, endpoint: str) -> list[int]:
        """
        Fetch story IDs from HN Firebase API.
        
        Args:
            endpoint: One of 'topstories', 'askstories', 'showstories', 'jobstories'.
            
        Returns:
            List of HN item IDs.
        """
        url = f"{BASE_URL_FIREBASE}/{endpoint}.json"
        logger.info(f"Fetching {endpoint} IDs")
        
        data = await self._request_with_retry(url)
        
        if data is None:
            logger.error(f"Failed to fetch {endpoint}")
            return []
        
        return data
    
    async def search_algolia(self, query: str, tags: str = "story") -> list[dict[str, Any]]:
        """
        Search HN via Algolia API.
        
        Args:
            query: Search query string.
            tags: Filter tags (e.g., 'story', 'comment').
            
        Returns:
            List of search result dicts.
        """
        url = f"{BASE_URL_ALGOLIA}/search"
        params = {"query": query, "tags": tags, "hitsPerPage": 50}
        
        logger.info(f"Algolia search: query='{query}', tags='{tags}'")
        
        client = await self._get_client()
        
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", [])
            logger.info(f"Algolia search returned {len(hits)} results")
            return hits
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Algolia search failed: {e}")
            raise HNBaseError(f"Algolia search failed: {e}") from e
    
    async def fetch_algolia_comments(self, objectID: str) -> list[dict[str, Any]]:
        """
        Fetch full comment tree for a thread via Algolia.
        
        Args:
            objectID: Algolia object ID (HN item ID as string).
            
        Returns:
            List of comment dicts.
        """
        url = f"{BASE_URL_ALGOLIA}/search"
        params = {
            "query": "",
            "tags": f"comment_{objectID}",
            "hitsPerPage": 100,
        }
        
        logger.info(f"Fetching Algolia comments for objectID={objectID}")
        
        client = await self._get_client()
        
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", [])
            logger.info(f"Algolia comments returned {len(hits)} results")
            return hits
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Algolia comments fetch failed: {e}")
            raise HNBaseError(f"Algolia comments fetch failed: {e}") from e
