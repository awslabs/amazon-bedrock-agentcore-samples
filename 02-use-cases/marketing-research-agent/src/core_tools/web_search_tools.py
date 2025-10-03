import asyncio
import re
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
from ddgs import DDGS

import logging
import httpx
from bs4 import BeautifulSoup
from strands.tools import tool


logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Data class for search result information."""
    title: str
    link: str
    snippet: str
    position: int


class RateLimiter:


    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    async def acquire(self):
        now = datetime.now()
        # Remove requests older than 1 minute
        self.requests = [
            req for req in self.requests if now - req < timedelta(minutes=1)
        ]

        if len(self.requests) >= self.requests_per_minute:
            # Wait until we can make another request
            wait_time = 60 - (now - self.requests[0]).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.requests.append(now)


class DDGSEngine:
    """DDGS search implementation with rate limiting and result formatting"""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def __init__(self):
        self.rate_limiter = RateLimiter()

    def format_results_for_llm(self, results: List[SearchResult]) -> str:
        """Format results in a natural language style that's easier for LLMs to process"""
        if not results:
            return "No results were found for your search query. This could be due to bot detection or the query returned no matches. Please try rephrasing your search or try again in a few minutes."

        output = []
        output.append(f"Found {len(results)} search results:\n")

        for result in results:
            output.append(f"{result.position}. {result.title}")
            output.append(f"   URL: {result.link}")
            output.append(f"   Summary: {result.snippet}")
            output.append("")  # Empty line between results

        return "\n".join(output)

    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Perform a internet search and return structured results"""
        logger.info(f"Starting DDGS search for query: '{query}' with max_results: {max_results}")
        try:
            # Apply rate limiting
            logger.debug("Applying rate limiting")
            await self.rate_limiter.acquire()

            # Create form data for POST request
            data = {
                "q": query,
                "b": "",
                "kl": "",
            }

            search_results = DDGS().text(query, max_results=max_results)
            results = []
            for result in search_results:

                results.append(
                    SearchResult(
                        title=result['title'],
                        link=result['href'],
                        snippet=result['body'],
                        position=len(results) + 1,
                    )
                )

                if len(results) >= max_results:
                    break

            logger.info(f"Successfully parsed {len(results)} search results")
            return results

        except httpx.TimeoutException:
            logger.warning(f"Timeout occurred while searching for query: '{query}'")
            return []
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while searching for query: '{query}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error occurred while searching for query: '{query}': {e}")
            traceback.print_exc(file=sys.stderr)
            return []


class WebContentFetcher:
    """Web content fetcher with rate limiting and intelligent text extraction"""

    def __init__(self):
        self.rate_limiter = RateLimiter(requests_per_minute=20)

    async def fetch_and_parse(self, url: str) -> str:
        """Fetch and parse content from a webpage"""
        logger.info(f"Fetching content from URL: {url}")
        try:
            logger.debug("Applying rate limiting for web content fetch")
            await self.rate_limiter.acquire()

            logger.debug(f"Making GET request to: {url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    follow_redirects=True,
                    timeout=30.0,
                )
                response.raise_for_status()
                logger.debug(f"Successfully fetched content from {url}, status: {response.status_code}")

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "header", "footer"]):
                element.decompose()

            # Get the text content
            text = soup.get_text()

            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            # Remove extra whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Truncate if too long
            if len(text) > 8000:
                logger.debug(f"Content truncated from {len(text)} to 8000 characters")
                text = text[:8000] + "... [content truncated]"

            logger.info(f"Successfully extracted {len(text)} characters of content from {url}")
            return text

        except httpx.TimeoutException:
            logger.warning(f"Timeout occurred while fetching content from: {url}")
            return "Error: The request timed out while trying to fetch the webpage."
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred while fetching content from {url}: {e}")
            return f"Error: Could not access the webpage ({str(e)})"
        except Exception as e:
            logger.error(f"Unexpected error occurred while fetching content from {url}: {e}")
            return f"Error: An unexpected error occurred while fetching the webpage ({str(e)})"


searcher = DDGSEngine()
fetcher = WebContentFetcher()


@tool()
async def web_search(query: str, max_results: int = 10) -> str:
    """
    Search the web for real-time information using web search engine and return formatted search results.

    This tool provides free web search capabilities without requiring API keys.
    It searches the internet and returns structured results with titles, URLs, and snippets.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10, max: 20)

    Returns:
        Formatted string containing search results with titles, URLs, and snippets.
    """
    logger.info(f"Web search tool called with query: '{query}', max_results: {max_results}")
    try:
        # Limit max_results to prevent abuse
        max_results = min(max_results, 20)

        results = await searcher.search(query, max_results)
        formatted_results = searcher.format_results_for_llm(results)
        logger.info(f"Web search completed successfully, returning {len(results)} results")
        return formatted_results
    except Exception as e:
        logger.error(f"Error in web_search tool: {e}")
        traceback.print_exc(file=sys.stderr)
        return f"An error occurred while searching: {str(e)}"


@tool
async def web_extract(url: str) -> str:
    """
    Fetch and parse content from a webpage URL.

    This tool fetches content from any webpage and extracts the main text content,
    removing navigation, headers, footers, and other non-content elements.

    Args:
        url: The webpage URL to fetch content from

    Returns:
        Cleaned and formatted text content from the webpage.
    """
    logger.info(f"Webpage content fetch tool called for URL: {url}")
    result = await fetcher.fetch_and_parse(url)
    logger.info(f"Webpage content fetch completed for URL: {url}")
    return result


@tool
async def web_crawl(query: str, max_results: int = 5, fetch_first: int = 2) -> str:
    """
    Search the web for real-time information using diverse search engine and automatically fetch content from the top results.

    This is a convenience tool that combines search and content fetching.
    It searches for the query and then fetches the full content from the top results.

    Args:
        query: The search query to execute with internet search engines. This should be a clear, specific question or search term.
        max_results: Maximum number of search results to return between 0 and 10 (default: 5, max: 10)
        fetch_first: Number of top results to fetch full content from (default: 2, max: 5)

    Returns:
        Combined search results and full content from top results.
    """
    try:
        # Limit parameters to prevent abuse
        max_results = min(max_results, 10)
        fetch_first = min(fetch_first, 5)

        # First, get search results
        results = await searcher.search(query, max_results)

        if not results:
            return "No search results found for the query."

        output = []
        output.append(f"Search Results for '{query}':")
        output.append("=" * 50)
        output.append("")

        # Add search results summary
        for result in results:
            output.append(f"{result.position}. {result.title}")
            output.append(f"   URL: {result.link}")
            output.append(f"   Summary: {result.snippet}")
            output.append("")

        # Fetch full content from top results
        if fetch_first > 0:
            output.append("Full Content from Top Results:")
            output.append("=" * 50)
            output.append("")

            for i, result in enumerate(results[:fetch_first]):
                output.append(f"Content from Result {i + 1}: {result.title}")
                output.append(f"URL: {result.link}")
                output.append("-" * 30)

                content = await fetcher.fetch_and_parse(result.link)
                output.append(content)
                output.append("")
                output.append("=" * 50)
                output.append("")

        return "\n".join(output)

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return f"An error occurred during search and fetch: {str(e)}"