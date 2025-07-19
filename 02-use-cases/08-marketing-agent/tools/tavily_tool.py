import os
from tavily import TavilyClient
from strands import tool

# Initialize the Tavily API client
tavily_api_key = os.getenv("TAVILY_API_KEY")
if not tavily_api_key:
    raise ValueError("TAVILY_API_KEY is not set. Please add it to your .env file.")
tavily_client = TavilyClient(api_key=tavily_api_key)


# --- Web Search Tool ---

def format_search_results_for_agent(tavily_result):
    """
    Format Tavily search results into a well-structured string for language models.
    """
    if (
        not tavily_result
        or "results" not in tavily_result
        or not tavily_result["results"]
    ):
        return "No search results found."

    formatted_results = []
    for i, doc in enumerate(tavily_result["results"], 1):
        title = doc.get("title", "No title")
        url = doc.get("url", "No URL")
        formatted_doc = f"\nRESULT {i}:\nTitle: {title}\nURL: {url}\n"
        raw_content = doc.get("raw_content")
        if raw_content and raw_content.strip():
            formatted_doc += f"Raw Content: {raw_content.strip()}\n"
        else:
            content = doc.get("content", "").strip()
            formatted_doc += f"Content: {content}\n"
        formatted_results.append(formatted_doc)
    return "\n" + "\n".join(formatted_results)

@tool
def web_search(
    query: str, time_range: str | None = None, include_domains: str | None = None
) -> str:
    """Perform a web search. Returns the search results as a string, with the title, url, and content of each result ranked by relevance."""
    try:
        search_result = tavily_client.search(
            query=query,
            max_results=10,
            search_depth="advanced",
            include_answer=True,
            time_range=time_range,
            include_domains=include_domains,
        )
        formatted_results = format_search_results_for_agent(search_result)
        return formatted_results
    except Exception as e:
        return f"Error during web search: {e}"

# --- Web Extract Tool ---

def format_extract_results_for_agent(tavily_result):
    """
    Format Tavily extract results into a well-structured string for language models.
    """
    if not tavily_result or "results" not in tavily_result:
        return "No extract results found."
    formatted_results = []
    results = tavily_result.get("results", [])
    for i, doc in enumerate(results, 1):
        url = doc.get("url", "No URL")
        raw_content = doc.get("raw_content", "")
        formatted_doc = f"\nEXTRACT RESULT {i}:\nURL: {url}\n"
        if raw_content:
            if len(raw_content) > 5000:
                formatted_doc += f"Content: {raw_content[:5000]}...\n"
            else:
                formatted_doc += f"Content: {raw_content}\n"
        else:
            formatted_doc += "Content: No content extracted\n"
        formatted_results.append(formatted_doc)
    return "\n" + "".join(formatted_results)


@tool
def web_extract(
    urls: str | list[str], extract_depth: str = "basic"
) -> str:
    """Extract content from one or more web pages using Tavily's extract API."""
    try:
        if isinstance(urls, str):
            urls_list = [urls]
        else:
            urls_list = urls
        cleaned_urls = []
        for url in urls_list:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            cleaned_urls.append(url)
        api_response = tavily_client.extract(
            urls=cleaned_urls,
            extract_depth=extract_depth,
        )
        return format_extract_results_for_agent(api_response)
    except Exception as e:
        return f"Error during extraction: {e}"


# --- Web Crawl Tool ---

def format_crawl_results_for_agent(tavily_result):
    """
    Format Tavily crawl results into a well-structured string for language models.
    """
    if not tavily_result:
        return "No crawl results found."
    formatted_results = []
    for i, doc in enumerate(tavily_result, 1):
        url = doc.get("url", "No URL")
        raw_content = doc.get("raw_content", "")
        formatted_doc = f"\nRESULT {i}:\nURL: {url}\n"
        if raw_content:
            title_line = raw_content.split("\n")[0] if raw_content else "No title"
            formatted_doc += f"Title: {title_line}\n"
            formatted_doc += (
                f"Content: {raw_content[:4000]}...\n"
                if len(raw_content) > 4000
                else f"Content: {raw_content}\n"
            )
        formatted_results.append(formatted_doc)
    return "\n" + "-" * 40 + "\n".join(formatted_results)


@tool
def web_crawl(url: str, instructions: str | None = None) -> str:
    """
    Crawls a given URL, processes the results, and formats them into a string.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        api_response = tavily_client.crawl(
            url=url,
            max_depth=2,
            limit=20,
            instructions=instructions,
        )
        tavily_results = (
            api_response.get("results")
            if isinstance(api_response, dict)
            else api_response
        )
        return format_crawl_results_for_agent(tavily_results)
    except Exception as e:
        return f"Error: {e}\nURL attempted: {url}\nFailed to crawl the website."
