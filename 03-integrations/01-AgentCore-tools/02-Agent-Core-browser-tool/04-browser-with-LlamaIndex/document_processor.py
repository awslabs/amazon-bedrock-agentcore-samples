"""
Document processing integration for LlamaIndex + AgentCore browser tool.

This module provides comprehensive document processing capabilities that convert
web content extracted via AgentCore browser tool into LlamaIndex Document objects
with proper metadata, batch processing, and content analysis.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import base64
import re
from urllib.parse import urljoin, urlparse

# LlamaIndex imports
try:
    from llama_index.core.schema import Document, BaseNode, TextNode
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.core.extractors import BaseExtractor
except ImportError:
    # Fallback for different LlamaIndex versions
    try:
        from llama_index import Document, BaseNode, TextNode
        from llama_index.node_parser import SimpleNodeParser
        from llama_index.extractors import BaseExtractor
    except ImportError:
        # Mock classes for testing when LlamaIndex is not available
        class Document:
            def __init__(self, text: str, metadata: Dict[str, Any] = None, **kwargs):
                self.text = text
                self.metadata = metadata or {}
                
        class BaseNode:
            pass
            
        class TextNode(BaseNode):
            def __init__(self, text: str, metadata: Dict[str, Any] = None, **kwargs):
                self.text = text
                self.metadata = metadata or {}
                
        class SimpleNodeParser:
            def get_nodes_from_documents(self, documents: List[Document]) -> List[TextNode]:
                return [TextNode(text=doc.text, metadata=doc.metadata) for doc in documents]
                
        class BaseExtractor:
            pass

from interfaces import IBrowserClient, BrowserResponse, ElementSelector
from exceptions import AgentCoreBrowserError, BrowserErrorType
from client import AgentCoreBrowserClient
from config import ConfigurationManager


logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of web content that can be processed."""
    HTML = "html"
    TEXT = "text"
    JSON = "json"
    XML = "xml"
    MARKDOWN = "markdown"
    PDF = "pdf"
    UNKNOWN = "unknown"


class ProcessingStatus(Enum):
    """Status of document processing operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WebContentMetadata:
    """Metadata extracted from web content via AgentCore browser tool."""
    source_url: str
    page_title: Optional[str] = None
    extraction_timestamp: Optional[datetime] = None
    content_type: ContentType = ContentType.HTML
    content_length: int = 0
    content_hash: Optional[str] = None
    page_language: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: List[str] = field(default_factory=list)
    canonical_url: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    viewport_size: Optional[Dict[str, int]] = None
    user_agent: Optional[str] = None
    response_status: Optional[int] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    links_count: int = 0
    images_count: int = 0
    forms_count: int = 0
    scripts_count: int = 0
    stylesheets_count: int = 0
    dom_depth: int = 0
    load_time_ms: Optional[int] = None
    screenshot_available: bool = False
    captcha_detected: bool = False
    error_messages: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary format."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result


@dataclass
class ProcessingResult:
    """Result of document processing operation."""
    url: str
    status: ProcessingStatus
    document: Optional[Document] = None
    metadata: Optional[WebContentMetadata] = None
    error_message: Optional[str] = None
    processing_time_ms: int = 0
    nodes_created: int = 0
    content_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format."""
        return {
            'url': self.url,
            'status': self.status.value,
            'document_available': self.document is not None,
            'metadata_available': self.metadata is not None,
            'error_message': self.error_message,
            'processing_time_ms': self.processing_time_ms,
            'nodes_created': self.nodes_created,
            'content_size': self.content_size
        }


class WebContentDocument(Document):
    """
    Extended Document class for web content from AgentCore browser tool.
    
    This class extends LlamaIndex's Document with additional web-specific
    metadata and functionality for content extracted via AgentCore browser tool.
    """
    
    def __init__(self,
                 text: str,
                 source_url: str,
                 page_title: Optional[str] = None,
                 extraction_timestamp: Optional[datetime] = None,
                 screenshot_data: Optional[bytes] = None,
                 dom_structure: Optional[Dict] = None,
                 web_metadata: Optional[WebContentMetadata] = None,
                 **kwargs):
        """
        Initialize WebContentDocument with web-specific data.
        
        Args:
            text: Extracted text content from the web page
            source_url: URL of the source web page
            page_title: Title of the web page
            extraction_timestamp: When the content was extracted
            screenshot_data: Optional screenshot data from AgentCore browser tool
            dom_structure: Optional DOM structure information
            web_metadata: Additional web-specific metadata
            **kwargs: Additional arguments passed to parent Document class
        """
        # Store browser-specific data in metadata to avoid Pydantic validation issues
        base_metadata = {
            "source_url": source_url,
            "page_title": page_title,
            "extraction_timestamp": extraction_timestamp.isoformat() if extraction_timestamp else None,
            "extraction_method": "agentcore_browser_tool",
            "document_type": "web_content",
            **kwargs.get("metadata", {})
        }
        
        # Add web metadata if provided
        if web_metadata:
            base_metadata.update(web_metadata.to_dict())
        
        # Store additional data in metadata to avoid Pydantic issues
        if screenshot_data:
            base_metadata["has_screenshot"] = True
            base_metadata["screenshot_size"] = len(screenshot_data)
        else:
            base_metadata["has_screenshot"] = False
            
        if dom_structure:
            base_metadata["has_dom_structure"] = True
            base_metadata["dom_elements_count"] = len(dom_structure) if isinstance(dom_structure, dict) else 0
        else:
            base_metadata["has_dom_structure"] = False
        
        # Initialize parent Document
        super().__init__(text=text, metadata=base_metadata, **kwargs)
        
        # Store additional browser-specific data as private attributes to avoid Pydantic validation
        self._screenshot_data = screenshot_data
        self._dom_structure = dom_structure
        self._web_metadata = web_metadata
        self._source_url = source_url
        self._extraction_timestamp = extraction_timestamp or datetime.now(timezone.utc)
    
    @property
    def screenshot_data(self) -> Optional[bytes]:
        """Get screenshot data."""
        return self._screenshot_data
    
    @property
    def dom_structure(self) -> Optional[Dict]:
        """Get DOM structure."""
        return self._dom_structure
    
    @property
    def web_metadata(self) -> Optional[WebContentMetadata]:
        """Get web metadata."""
        return self._web_metadata
    
    @property
    def source_url(self) -> str:
        """Get source URL."""
        return self._source_url
    
    @property
    def extraction_timestamp(self) -> datetime:
        """Get extraction timestamp."""
        return self._extraction_timestamp
    
    def get_content_hash(self) -> str:
        """Generate hash of the document content."""
        content_str = f"{self.text}{self._source_url}{self._extraction_timestamp.isoformat()}"
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def get_screenshot_base64(self) -> Optional[str]:
        """Get screenshot data as base64 string."""
        if self._screenshot_data:
            return base64.b64encode(self._screenshot_data).decode('utf-8')
        return None
    
    def extract_links(self) -> List[str]:
        """Extract links from DOM structure if available."""
        if not self._dom_structure:
            return []
        
        links = []
        # Extract links from DOM structure
        if 'links' in self._dom_structure:
            for link in self._dom_structure['links']:
                if isinstance(link, dict) and 'href' in link:
                    # Convert relative URLs to absolute
                    href = link['href']
                    if href.startswith('http'):
                        links.append(href)
                    else:
                        links.append(urljoin(self._source_url, href))
        
        return links
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about the document."""
        return {
            'content_length': len(self.text),
            'word_count': len(self.text.split()),
            'line_count': len(self.text.splitlines()),
            'has_screenshot': self._screenshot_data is not None,
            'has_dom_structure': self._dom_structure is not None,
            'links_count': len(self.extract_links()),
            'content_hash': self.get_content_hash()
        }


class WebContentExtractor:
    """
    Web content metadata extractor for AgentCore browser tool content.
    
    This extractor analyzes web content and extracts additional metadata
    that can be used for indexing and retrieval. Simplified to avoid
    LlamaIndex BaseExtractor abstract method requirements.
    """
    
    def __init__(self, 
                 extract_links: bool = True,
                 extract_images: bool = True,
                 extract_headings: bool = True,
                 max_links: int = 100):
        """
        Initialize web content extractor.
        
        Args:
            extract_links: Whether to extract links from content
            extract_images: Whether to extract image information
            extract_headings: Whether to extract heading structure
            max_links: Maximum number of links to extract
        """
        self.extract_links = extract_links
        self.extract_images = extract_images
        self.extract_headings = extract_headings
        self.max_links = max_links
    
    def extract(self, nodes: List[Union[BaseNode, Document]]) -> List[Dict[str, Any]]:
        """
        Extract metadata from web content nodes.
        
        Args:
            nodes: List of nodes to extract metadata from
            
        Returns:
            List of metadata dictionaries
        """
        metadata_list = []
        
        for node in nodes:
            if isinstance(node, (Document, WebContentDocument)):
                metadata = self._extract_from_document(node)
                metadata_list.append(metadata)
            else:
                # Handle other node types
                metadata_list.append({})
        
        return metadata_list
    
    def _extract_from_document(self, document: Union[Document, WebContentDocument]) -> Dict[str, Any]:
        """Extract metadata from a document."""
        metadata = {}
        
        # Extract basic text statistics
        text = document.text
        metadata.update({
            'word_count': len(text.split()),
            'char_count': len(text),
            'line_count': len(text.splitlines()),
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()])
        })
        
        # Extract headings if enabled
        if self.extract_headings:
            headings = self._extract_headings(text)
            metadata['headings'] = headings
            metadata['heading_count'] = len(headings)
        
        # Extract links if enabled and available
        if self.extract_links and isinstance(document, WebContentDocument):
            links = document.extract_links()[:self.max_links]
            metadata['extracted_links'] = links
            metadata['links_count'] = len(links)
        
        # Extract language information
        language = self._detect_language(text)
        if language:
            metadata['detected_language'] = language
        
        return metadata
    
    def _extract_headings(self, text: str) -> List[Dict[str, Any]]:
        """Extract heading structure from text."""
        headings = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for markdown-style headings
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                heading_text = line.lstrip('#').strip()
                if heading_text:
                    headings.append({
                        'level': level,
                        'text': heading_text,
                        'line_number': i + 1
                    })
            # Look for title-case lines that might be headings
            elif (len(line) > 0 and len(line) < 100 and 
                  line.istitle() and not line.endswith('.')):
                headings.append({
                    'level': 0,  # Unknown level
                    'text': line,
                    'line_number': i + 1,
                    'inferred': True
                })
        
        return headings
    
    def _detect_language(self, text: str) -> Optional[str]:
        """Simple language detection based on common words."""
        # This is a very basic implementation
        # In production, you might want to use a proper language detection library
        
        if not text or len(text) < 50:
            return None
        
        # Common English words
        english_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
        
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return None
        
        english_count = sum(1 for word in words[:100] if word in english_words)
        english_ratio = english_count / min(len(words), 100)
        
        if english_ratio > 0.3:
            return 'en'
        
        return 'unknown'


class DocumentProcessor:
    """
    Main document processor for converting AgentCore browser tool content to LlamaIndex documents.
    
    This class handles the complete pipeline from web content extraction via AgentCore
    browser tool to LlamaIndex Document creation with comprehensive metadata.
    """
    
    def __init__(self, 
                 browser_client: Optional[IBrowserClient] = None,
                 config_path: Optional[str] = None,
                 node_parser: Optional[SimpleNodeParser] = None,
                 content_extractor: Optional[WebContentExtractor] = None,
                 max_content_length: int = 1000000,  # 1MB
                 include_screenshots: bool = True,
                 include_dom_structure: bool = True):
        """
        Initialize document processor.
        
        Args:
            browser_client: AgentCore browser client for web operations (optional, will create if None)
            config_path: Path to configuration file (optional, uses default if None)
            node_parser: Optional LlamaIndex node parser
            content_extractor: Optional web content extractor
            max_content_length: Maximum content length to process
            include_screenshots: Whether to capture screenshots
            include_dom_structure: Whether to include DOM structure
        """
        # Create browser client if not provided
        if browser_client is None:
            config_manager = ConfigurationManager(config_path or "agentcore_config.json")
            browser_client = AgentCoreBrowserClient(config_manager=config_manager)
        
        self.browser_client = browser_client
        self.node_parser = node_parser or SimpleNodeParser()
        self.content_extractor = content_extractor or WebContentExtractor()
        self.max_content_length = max_content_length
        self.include_screenshots = include_screenshots
        self.include_dom_structure = include_dom_structure
        
        # Processing statistics
        self._stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total_content_size': 0,
            'total_processing_time_ms': 0
        }
    
    async def process_url(self, 
                         url: str,
                         wait_for_load: bool = True,
                         timeout: Optional[int] = None,
                         extract_metadata: bool = True) -> ProcessingResult:
        """
        Process a single URL and convert to LlamaIndex document.
        
        Args:
            url: URL to process
            wait_for_load: Whether to wait for page load
            timeout: Navigation timeout in seconds
            extract_metadata: Whether to extract additional metadata
            
        Returns:
            ProcessingResult with document and metadata
        """
        start_time = datetime.now()
        result = ProcessingResult(url=url, status=ProcessingStatus.PROCESSING)
        
        try:
            logger.info(f"Processing URL: {url}")
            
            # Navigate to the URL using AgentCore browser tool
            nav_response = await self.browser_client.navigate(
                url=url,
                wait_for_load=wait_for_load,
                timeout=timeout
            )
            
            if not nav_response.success:
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Navigation failed: {nav_response.error_message}"
                return result
            
            # Extract text content
            text_response = await self.browser_client.extract_text()
            if not text_response.success:
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Text extraction failed: {text_response.error_message}"
                return result
            
            # Extract text from the parsed response
            text_extraction_result = text_response.data.get('text_extraction_result', {})
            text_content = text_extraction_result.get('text', '')
            
            # Check content length
            if len(text_content) > self.max_content_length:
                logger.warning(f"Content too large ({len(text_content)} chars), truncating")
                text_content = text_content[:self.max_content_length]
            
            if not text_content.strip():
                result.status = ProcessingStatus.SKIPPED
                result.error_message = "No text content found"
                return result
            
            # Get page information from navigation response
            nav_result = nav_response.data.get('navigation_result', {})
            page_info = {
                'title': nav_result.get('title'),
                'url': nav_result.get('url'),
                'status_code': nav_result.get('status_code'),
                'load_time_ms': nav_result.get('load_time_ms')
            }
            
            # Capture screenshot if enabled
            screenshot_data = None
            if self.include_screenshots:
                try:
                    screenshot_response = await self.browser_client.take_screenshot()
                    if screenshot_response.success:
                        screenshot_result = screenshot_response.data.get('screenshot_result', {})
                        screenshot_data = screenshot_result.get('image_data')
                        if isinstance(screenshot_data, str):
                            screenshot_data = base64.b64decode(screenshot_data)
                except Exception as e:
                    logger.warning(f"Failed to capture screenshot for {url}: {e}")
            
            # Extract DOM structure if enabled
            dom_structure = None
            if self.include_dom_structure:
                try:
                    # This would be implemented based on AgentCore's DOM analysis capabilities
                    dom_structure = page_info.get('dom_structure', {})
                except Exception as e:
                    logger.warning(f"Failed to extract DOM structure for {url}: {e}")
            
            # Create web content metadata
            web_metadata = self._create_web_metadata(
                url=url,
                page_info=page_info,
                text_content=text_content,
                nav_response=nav_response,
                screenshot_available=screenshot_data is not None
            )
            
            # Create WebContentDocument
            document = WebContentDocument(
                text=text_content,
                source_url=url,
                page_title=page_info.get('title'),
                extraction_timestamp=datetime.now(timezone.utc),
                screenshot_data=screenshot_data,
                dom_structure=dom_structure,
                web_metadata=web_metadata
            )
            
            # Extract additional metadata if enabled
            if extract_metadata:
                try:
                    additional_metadata = self.content_extractor.extract([document])
                    if additional_metadata:
                        document.metadata.update(additional_metadata[0])
                except Exception as e:
                    logger.warning(f"Failed to extract additional metadata: {e}")
            
            # Update result
            result.status = ProcessingStatus.COMPLETED
            result.document = document
            result.metadata = web_metadata
            result.content_size = len(text_content)
            
            # Update statistics
            self._stats['successful'] += 1
            self._stats['total_content_size'] += len(text_content)
            
            logger.info(f"Successfully processed {url} ({len(text_content)} chars)")
            
        except Exception as e:
            logger.error(f"Failed to process {url}: {e}")
            result.status = ProcessingStatus.FAILED
            result.error_message = str(e)
            self._stats['failed'] += 1
        
        finally:
            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds() * 1000
            result.processing_time_ms = int(processing_time)
            
            self._stats['total_processed'] += 1
            self._stats['total_processing_time_ms'] += result.processing_time_ms
        
        return result
    
    async def process_urls_batch(self, 
                                urls: List[str],
                                max_concurrent: int = 5,
                                wait_for_load: bool = True,
                                timeout: Optional[int] = None,
                                extract_metadata: bool = True) -> List[ProcessingResult]:
        """
        Process multiple URLs concurrently using AgentCore browser tool.
        
        Args:
            urls: List of URLs to process
            max_concurrent: Maximum concurrent processing sessions
            wait_for_load: Whether to wait for page load
            timeout: Navigation timeout in seconds
            extract_metadata: Whether to extract additional metadata
            
        Returns:
            List of ProcessingResult objects
        """
        logger.info(f"Starting batch processing of {len(urls)} URLs with max_concurrent={max_concurrent}")
        
        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(url: str) -> ProcessingResult:
            async with semaphore:
                # For batch processing, reuse the same browser client to avoid configuration issues
                # In production, you might want to create separate clients for true isolation
                return await self.process_url(
                    url=url,
                    wait_for_load=wait_for_load,
                    timeout=timeout,
                    extract_metadata=extract_metadata
                )
        
        # Process all URLs concurrently
        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing {urls[i]}: {result}")
                processed_results.append(ProcessingResult(
                    url=urls[i],
                    status=ProcessingStatus.FAILED,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        # Log batch processing summary
        successful = sum(1 for r in processed_results if r.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for r in processed_results if r.status == ProcessingStatus.FAILED)
        skipped = sum(1 for r in processed_results if r.status == ProcessingStatus.SKIPPED)
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed, {skipped} skipped")
        
        return processed_results
    
    def _create_web_metadata(self, 
                           url: str,
                           page_info: Dict[str, Any],
                           text_content: str,
                           nav_response: BrowserResponse,
                           screenshot_available: bool = False) -> WebContentMetadata:
        """
        Create comprehensive web metadata from AgentCore browser tool responses.
        
        Args:
            url: Source URL
            page_info: Page information from browser
            text_content: Extracted text content
            nav_response: Navigation response
            screenshot_available: Whether screenshot was captured
            
        Returns:
            WebContentMetadata object
        """
        # Parse URL for additional info
        parsed_url = urlparse(url)
        
        # Extract content type
        content_type = ContentType.HTML  # Default
        if 'content_type' in page_info:
            content_type_str = page_info['content_type'].lower()
            if 'json' in content_type_str:
                content_type = ContentType.JSON
            elif 'xml' in content_type_str:
                content_type = ContentType.XML
            elif 'text' in content_type_str:
                content_type = ContentType.TEXT
        
        # Create metadata object
        metadata = WebContentMetadata(
            source_url=url,
            page_title=page_info.get('title'),
            extraction_timestamp=datetime.now(timezone.utc),
            content_type=content_type,
            content_length=len(text_content),
            content_hash=hashlib.sha256(text_content.encode()).hexdigest(),
            page_language=page_info.get('language'),
            meta_description=page_info.get('meta_description'),
            meta_keywords=page_info.get('meta_keywords', []),
            canonical_url=page_info.get('canonical_url'),
            author=page_info.get('author'),
            viewport_size=page_info.get('viewport_size'),
            user_agent=page_info.get('user_agent'),
            response_status=page_info.get('status_code'),
            response_headers=page_info.get('headers', {}),
            links_count=page_info.get('links_count', 0),
            images_count=page_info.get('images_count', 0),
            forms_count=page_info.get('forms_count', 0),
            scripts_count=page_info.get('scripts_count', 0),
            stylesheets_count=page_info.get('stylesheets_count', 0),
            dom_depth=page_info.get('dom_depth', 0),
            load_time_ms=nav_response.data.get('load_time_ms'),
            screenshot_available=screenshot_available,
            captcha_detected=page_info.get('captcha_detected', False)
        )
        
        # Parse dates if available
        if 'published_date' in page_info:
            try:
                metadata.published_date = datetime.fromisoformat(page_info['published_date'])
            except (ValueError, TypeError):
                pass
        
        if 'modified_date' in page_info:
            try:
                metadata.modified_date = datetime.fromisoformat(page_info['modified_date'])
            except (ValueError, TypeError):
                pass
        
        return metadata
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self._stats.copy()
        if stats['total_processed'] > 0:
            stats['success_rate'] = stats['successful'] / stats['total_processed']
            stats['average_processing_time_ms'] = stats['total_processing_time_ms'] / stats['total_processed']
            stats['average_content_size'] = stats['total_content_size'] / stats['successful'] if stats['successful'] > 0 else 0
        else:
            stats['success_rate'] = 0.0
            stats['average_processing_time_ms'] = 0.0
            stats['average_content_size'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self._stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'total_content_size': 0,
            'total_processing_time_ms': 0
        }


class DocumentPipeline:
    """
    Complete document processing pipeline for web content.
    
    This class provides a high-level interface for processing web content
    from URLs into LlamaIndex documents with full metadata extraction.
    """
    
    def __init__(self, 
                 browser_client: Optional[IBrowserClient] = None,
                 config_path: Optional[str] = None,
                 processor_config: Optional[Dict[str, Any]] = None):
        """
        Initialize document pipeline.
        
        Args:
            browser_client: Optional browser client, creates default if None
            config_path: Path to configuration file (optional)
            processor_config: Optional processor configuration
        """
        self.browser_client = browser_client
        self.config_path = config_path
        self.processor_config = processor_config or {}
        self._processor: Optional[DocumentProcessor] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.browser_client:
            config_manager = ConfigurationManager(self.config_path or "agentcore_config.json")
            self.browser_client = AgentCoreBrowserClient(config_manager=config_manager)
        
        if hasattr(self.browser_client, '__aenter__'):
            await self.browser_client.__aenter__()
        
        # Initialize processor
        self._processor = DocumentProcessor(
            browser_client=self.browser_client,
            **self.processor_config
        )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser_client and hasattr(self.browser_client, '__aexit__'):
            await self.browser_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def process_single_url(self, url: str, **kwargs) -> ProcessingResult:
        """Process a single URL."""
        if not self._processor:
            raise RuntimeError("Pipeline not initialized. Use async context manager.")
        
        return await self._processor.process_url(url, **kwargs)
    
    async def process_multiple_urls(self, urls: List[str], **kwargs) -> List[ProcessingResult]:
        """Process multiple URLs."""
        if not self._processor:
            raise RuntimeError("Pipeline not initialized. Use async context manager.")
        
        return await self._processor.process_urls_batch(urls, **kwargs)
    
    def get_successful_documents(self, results: List[ProcessingResult]) -> List[WebContentDocument]:
        """Extract successful documents from processing results."""
        return [
            result.document for result in results 
            if result.status == ProcessingStatus.COMPLETED and result.document
        ]
    
    def get_processing_summary(self, results: List[ProcessingResult]) -> Dict[str, Any]:
        """Get summary of processing results."""
        total = len(results)
        successful = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
        failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
        skipped = sum(1 for r in results if r.status == ProcessingStatus.SKIPPED)
        
        total_content_size = sum(r.content_size for r in results if r.content_size > 0)
        total_processing_time = sum(r.processing_time_ms for r in results)
        
        return {
            'total_urls': total,
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'success_rate': successful / total if total > 0 else 0.0,
            'total_content_size': total_content_size,
            'total_processing_time_ms': total_processing_time,
            'average_processing_time_ms': total_processing_time / total if total > 0 else 0.0,
            'failed_urls': [r.url for r in results if r.status == ProcessingStatus.FAILED],
            'error_messages': [r.error_message for r in results if r.error_message]
        }