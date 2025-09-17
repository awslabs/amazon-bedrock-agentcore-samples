"""
Incremental content processing for AgentCore browser tool integration.

This module provides incremental content processing capabilities that detect
changes in web content over time and update LlamaIndex documents accordingly.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import sqlite3
from pathlib import Path

from document_processor import (
    DocumentProcessor, WebContentDocument, WebContentMetadata,
    ProcessingResult, ProcessingStatus, DocumentPipeline
)
from interfaces import IBrowserClient
from exceptions import AgentCoreBrowserError
from client import AgentCoreBrowserClient
from config import ConfigurationManager


logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of content changes detected."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


class MonitoringStatus(Enum):
    """Status of content monitoring."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ContentSnapshot:
    """Snapshot of web content at a specific time."""
    url: str
    content_hash: str
    content_length: int
    page_title: Optional[str]
    last_modified: Optional[datetime]
    extraction_timestamp: datetime
    metadata_hash: str
    screenshot_hash: Optional[str] = None
    dom_structure_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'url': self.url,
            'content_hash': self.content_hash,
            'content_length': self.content_length,
            'page_title': self.page_title,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'extraction_timestamp': self.extraction_timestamp.isoformat(),
            'metadata_hash': self.metadata_hash,
            'screenshot_hash': self.screenshot_hash,
            'dom_structure_hash': self.dom_structure_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentSnapshot':
        """Create from dictionary."""
        return cls(
            url=data['url'],
            content_hash=data['content_hash'],
            content_length=data['content_length'],
            page_title=data.get('page_title'),
            last_modified=datetime.fromisoformat(data['last_modified']) if data.get('last_modified') else None,
            extraction_timestamp=datetime.fromisoformat(data['extraction_timestamp']),
            metadata_hash=data['metadata_hash'],
            screenshot_hash=data.get('screenshot_hash'),
            dom_structure_hash=data.get('dom_structure_hash')
        )


@dataclass
class ChangeDetectionResult:
    """Result of change detection analysis."""
    url: str
    change_type: ChangeType
    previous_snapshot: Optional[ContentSnapshot]
    current_snapshot: Optional[ContentSnapshot]
    changes_detected: List[str]
    confidence_score: float
    processing_required: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'url': self.url,
            'change_type': self.change_type.value,
            'previous_snapshot': self.previous_snapshot.to_dict() if self.previous_snapshot else None,
            'current_snapshot': self.current_snapshot.to_dict() if self.current_snapshot else None,
            'changes_detected': self.changes_detected,
            'confidence_score': self.confidence_score,
            'processing_required': self.processing_required
        }


@dataclass
class IncrementalProcessingResult:
    """Result of incremental processing operation."""
    url: str
    change_detection: ChangeDetectionResult
    processing_result: Optional[ProcessingResult] = None
    previous_document: Optional[WebContentDocument] = None
    updated_document: Optional[WebContentDocument] = None
    processing_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'url': self.url,
            'change_detection': self.change_detection.to_dict(),
            'processing_result': self.processing_result.to_dict() if self.processing_result else None,
            'has_previous_document': self.previous_document is not None,
            'has_updated_document': self.updated_document is not None,
            'processing_time_ms': self.processing_time_ms
        }


class ContentHistoryManager:
    """
    Manages content history and snapshots for change detection.
    
    This class handles storing and retrieving content snapshots to enable
    incremental processing and change detection over time.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize content history manager.
        
        Args:
            storage_path: Path to SQLite database for storing history
        """
        self.storage_path = storage_path or "content_history.db"
        self._db_path = Path(self.storage_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for content history."""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS content_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        content_length INTEGER NOT NULL,
                        page_title TEXT,
                        last_modified TEXT,
                        extraction_timestamp TEXT NOT NULL,
                        metadata_hash TEXT NOT NULL,
                        screenshot_hash TEXT,
                        dom_structure_hash TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(url, content_hash)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_url_timestamp 
                    ON content_snapshots(url, extraction_timestamp DESC)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_content_hash 
                    ON content_snapshots(content_hash)
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize content history database: {e}")
            raise
    
    def store_snapshot(self, snapshot: ContentSnapshot) -> bool:
        """
        Store a content snapshot.
        
        Args:
            snapshot: ContentSnapshot to store
            
        Returns:
            True if stored successfully, False if duplicate
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO content_snapshots 
                    (url, content_hash, content_length, page_title, last_modified,
                     extraction_timestamp, metadata_hash, screenshot_hash, dom_structure_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    snapshot.url,
                    snapshot.content_hash,
                    snapshot.content_length,
                    snapshot.page_title,
                    snapshot.last_modified.isoformat() if snapshot.last_modified else None,
                    snapshot.extraction_timestamp.isoformat(),
                    snapshot.metadata_hash,
                    snapshot.screenshot_hash,
                    snapshot.dom_structure_hash
                ))
                
                return conn.total_changes > 0
                
        except Exception as e:
            logger.error(f"Failed to store content snapshot for {snapshot.url}: {e}")
            return False
    
    def get_latest_snapshot(self, url: str) -> Optional[ContentSnapshot]:
        """
        Get the latest snapshot for a URL.
        
        Args:
            url: URL to get snapshot for
            
        Returns:
            Latest ContentSnapshot or None if not found
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM content_snapshots 
                    WHERE url = ? 
                    ORDER BY extraction_timestamp DESC 
                    LIMIT 1
                """, (url,))
                
                row = cursor.fetchone()
                if row:
                    return ContentSnapshot(
                        url=row['url'],
                        content_hash=row['content_hash'],
                        content_length=row['content_length'],
                        page_title=row['page_title'],
                        last_modified=datetime.fromisoformat(row['last_modified']) if row['last_modified'] else None,
                        extraction_timestamp=datetime.fromisoformat(row['extraction_timestamp']),
                        metadata_hash=row['metadata_hash'],
                        screenshot_hash=row['screenshot_hash'],
                        dom_structure_hash=row['dom_structure_hash']
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get latest snapshot for {url}: {e}")
            return None
    
    def get_snapshots_history(self, url: str, limit: int = 10) -> List[ContentSnapshot]:
        """
        Get snapshot history for a URL.
        
        Args:
            url: URL to get history for
            limit: Maximum number of snapshots to return
            
        Returns:
            List of ContentSnapshot objects in reverse chronological order
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM content_snapshots 
                    WHERE url = ? 
                    ORDER BY extraction_timestamp DESC 
                    LIMIT ?
                """, (url, limit))
                
                snapshots = []
                for row in cursor.fetchall():
                    snapshots.append(ContentSnapshot(
                        url=row['url'],
                        content_hash=row['content_hash'],
                        content_length=row['content_length'],
                        page_title=row['page_title'],
                        last_modified=datetime.fromisoformat(row['last_modified']) if row['last_modified'] else None,
                        extraction_timestamp=datetime.fromisoformat(row['extraction_timestamp']),
                        metadata_hash=row['metadata_hash'],
                        screenshot_hash=row['screenshot_hash'],
                        dom_structure_hash=row['dom_structure_hash']
                    ))
                
                return snapshots
                
        except Exception as e:
            logger.error(f"Failed to get snapshot history for {url}: {e}")
            return []
    
    def cleanup_old_snapshots(self, retention_days: int = 30) -> int:
        """
        Clean up old snapshots beyond retention period.
        
        Args:
            retention_days: Number of days to retain snapshots
            
        Returns:
            Number of snapshots deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM content_snapshots 
                    WHERE extraction_timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                logger.info(f"Cleaned up {deleted_count} old content snapshots")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old snapshots: {e}")
            return 0
    
    def get_monitored_urls(self) -> List[str]:
        """
        Get list of URLs that have been monitored.
        
        Returns:
            List of unique URLs
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute("SELECT DISTINCT url FROM content_snapshots ORDER BY url")
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get monitored URLs: {e}")
            return []


class ChangeDetector:
    """
    Detects changes in web content by comparing snapshots.
    
    This class analyzes content snapshots to determine what has changed
    and whether reprocessing is required.
    """
    
    def __init__(self, 
                 content_threshold: float = 0.1,
                 metadata_threshold: float = 0.05,
                 title_weight: float = 0.3,
                 content_weight: float = 0.5,
                 metadata_weight: float = 0.2):
        """
        Initialize change detector.
        
        Args:
            content_threshold: Threshold for content change detection (0-1)
            metadata_threshold: Threshold for metadata change detection (0-1)
            title_weight: Weight for title changes in confidence calculation
            content_weight: Weight for content changes in confidence calculation
            metadata_weight: Weight for metadata changes in confidence calculation
        """
        self.content_threshold = content_threshold
        self.metadata_threshold = metadata_threshold
        self.title_weight = title_weight
        self.content_weight = content_weight
        self.metadata_weight = metadata_weight
    
    def detect_changes(self, 
                      previous_snapshot: Optional[ContentSnapshot],
                      current_snapshot: ContentSnapshot) -> ChangeDetectionResult:
        """
        Detect changes between two content snapshots.
        
        Args:
            previous_snapshot: Previous snapshot (None for new content)
            current_snapshot: Current snapshot
            
        Returns:
            ChangeDetectionResult with detected changes
        """
        if not previous_snapshot:
            return ChangeDetectionResult(
                url=current_snapshot.url,
                change_type=ChangeType.ADDED,
                previous_snapshot=None,
                current_snapshot=current_snapshot,
                changes_detected=["New content detected"],
                confidence_score=1.0,
                processing_required=True
            )
        
        changes_detected = []
        confidence_scores = []
        
        # Check content changes
        if previous_snapshot.content_hash != current_snapshot.content_hash:
            changes_detected.append("Content hash changed")
            
            # Calculate content change confidence based on length difference
            length_diff = abs(current_snapshot.content_length - previous_snapshot.content_length)
            length_ratio = length_diff / max(previous_snapshot.content_length, 1)
            content_confidence = min(length_ratio * 2, 1.0)  # Scale to 0-1
            confidence_scores.append((content_confidence, self.content_weight))
        
        # Check title changes
        if previous_snapshot.page_title != current_snapshot.page_title:
            changes_detected.append("Page title changed")
            confidence_scores.append((1.0, self.title_weight))
        
        # Check metadata changes
        if previous_snapshot.metadata_hash != current_snapshot.metadata_hash:
            changes_detected.append("Metadata changed")
            confidence_scores.append((0.8, self.metadata_weight))
        
        # Check screenshot changes
        if (previous_snapshot.screenshot_hash != current_snapshot.screenshot_hash and
            previous_snapshot.screenshot_hash is not None and
            current_snapshot.screenshot_hash is not None):
            changes_detected.append("Screenshot changed")
            confidence_scores.append((0.6, 0.1))  # Lower weight for visual changes
        
        # Check DOM structure changes
        if (previous_snapshot.dom_structure_hash != current_snapshot.dom_structure_hash and
            previous_snapshot.dom_structure_hash is not None and
            current_snapshot.dom_structure_hash is not None):
            changes_detected.append("DOM structure changed")
            confidence_scores.append((0.7, 0.1))  # Lower weight for structural changes
        
        # Calculate overall confidence score
        if confidence_scores:
            weighted_sum = sum(score * weight for score, weight in confidence_scores)
            total_weight = sum(weight for _, weight in confidence_scores)
            overall_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            overall_confidence = 0.0
        
        # Determine change type and processing requirement
        if not changes_detected:
            change_type = ChangeType.UNCHANGED
            processing_required = False
        else:
            change_type = ChangeType.MODIFIED
            processing_required = overall_confidence >= self.content_threshold
        
        return ChangeDetectionResult(
            url=current_snapshot.url,
            change_type=change_type,
            previous_snapshot=previous_snapshot,
            current_snapshot=current_snapshot,
            changes_detected=changes_detected,
            confidence_score=overall_confidence,
            processing_required=processing_required
        )
    
    def should_reprocess(self, change_result: ChangeDetectionResult) -> bool:
        """
        Determine if content should be reprocessed based on changes.
        
        Args:
            change_result: ChangeDetectionResult to evaluate
            
        Returns:
            True if reprocessing is recommended
        """
        if change_result.change_type == ChangeType.ADDED:
            return True
        
        if change_result.change_type == ChangeType.UNCHANGED:
            return False
        
        # For modified content, check confidence threshold
        return change_result.confidence_score >= self.content_threshold


class IncrementalProcessor:
    """
    Main incremental content processor.
    
    This class orchestrates incremental content processing by combining
    change detection with document processing to efficiently update
    LlamaIndex documents when web content changes.
    """
    
    def __init__(self,
                 browser_client: Optional[IBrowserClient] = None,
                 config_path: Optional[str] = None,
                 history_manager: Optional[ContentHistoryManager] = None,
                 change_detector: Optional[ChangeDetector] = None,
                 document_processor: Optional[DocumentProcessor] = None,
                 storage_path: Optional[str] = None):
        """
        Initialize incremental processor.
        
        Args:
            browser_client: Browser client for web operations (optional, will create if None)
            config_path: Path to configuration file (optional)
            history_manager: Content history manager
            change_detector: Change detection engine
            document_processor: Document processor for creating LlamaIndex documents
            storage_path: Path for storing content history
        """
        # Create browser client if not provided
        if browser_client is None:
            config_manager = ConfigurationManager(config_path or "agentcore_config.json")
            browser_client = AgentCoreBrowserClient(config_manager=config_manager)
        
        self.browser_client = browser_client
        self.history_manager = history_manager or ContentHistoryManager(storage_path)
        self.change_detector = change_detector or ChangeDetector()
        self.document_processor = document_processor or DocumentProcessor(browser_client=browser_client)
        
        # Processing statistics
        self._stats = {
            'total_processed': 0,
            'new_content': 0,
            'modified_content': 0,
            'unchanged_content': 0,
            'processing_errors': 0,
            'total_processing_time_ms': 0
        }
    
    async def process_url_incremental(self, 
                                    url: str,
                                    force_reprocess: bool = False,
                                    **processing_kwargs) -> IncrementalProcessingResult:
        """
        Process a URL incrementally, only reprocessing if content has changed.
        
        Args:
            url: URL to process
            force_reprocess: Force reprocessing even if no changes detected
            **processing_kwargs: Additional arguments for document processing
            
        Returns:
            IncrementalProcessingResult with change detection and processing results
        """
        start_time = datetime.now()
        
        try:
            # Get previous snapshot
            previous_snapshot = self.history_manager.get_latest_snapshot(url)
            
            # Process current content to create snapshot
            processing_result = await self.document_processor.process_url(url, **processing_kwargs)
            
            if processing_result.status != ProcessingStatus.COMPLETED:
                # Return error result
                return IncrementalProcessingResult(
                    url=url,
                    change_detection=ChangeDetectionResult(
                        url=url,
                        change_type=ChangeType.UNCHANGED,
                        previous_snapshot=previous_snapshot,
                        current_snapshot=None,
                        changes_detected=[f"Processing failed: {processing_result.error_message}"],
                        confidence_score=0.0,
                        processing_required=False
                    ),
                    processing_result=processing_result,
                    processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                )
            
            # Create current snapshot from processing result
            current_snapshot = self._create_snapshot_from_result(processing_result)
            
            # Detect changes
            change_result = self.change_detector.detect_changes(previous_snapshot, current_snapshot)
            
            # Store current snapshot
            self.history_manager.store_snapshot(current_snapshot)
            
            # Determine if we need to update the document
            should_update = (force_reprocess or 
                           change_result.processing_required or 
                           change_result.change_type == ChangeType.ADDED)
            
            # Prepare result
            result = IncrementalProcessingResult(
                url=url,
                change_detection=change_result,
                processing_result=processing_result if should_update else None,
                updated_document=processing_result.document if should_update else None,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
            
            # Update statistics
            self._update_stats(change_result.change_type, result.processing_time_ms)
            
            logger.info(f"Incremental processing completed for {url}: {change_result.change_type.value}, "
                       f"confidence: {change_result.confidence_score:.2f}, "
                       f"reprocessed: {should_update}")
            
            return result
            
        except Exception as e:
            logger.error(f"Incremental processing failed for {url}: {e}")
            self._stats['processing_errors'] += 1
            
            return IncrementalProcessingResult(
                url=url,
                change_detection=ChangeDetectionResult(
                    url=url,
                    change_type=ChangeType.UNCHANGED,
                    previous_snapshot=None,
                    current_snapshot=None,
                    changes_detected=[f"Processing error: {str(e)}"],
                    confidence_score=0.0,
                    processing_required=False
                ),
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def process_urls_incremental(self,
                                     urls: List[str],
                                     max_concurrent: int = 5,
                                     force_reprocess: bool = False,
                                     **processing_kwargs) -> List[IncrementalProcessingResult]:
        """
        Process multiple URLs incrementally with concurrency control.
        
        Args:
            urls: List of URLs to process
            max_concurrent: Maximum concurrent processing operations
            force_reprocess: Force reprocessing even if no changes detected
            **processing_kwargs: Additional arguments for document processing
            
        Returns:
            List of IncrementalProcessingResult objects
        """
        logger.info(f"Starting incremental batch processing of {len(urls)} URLs")
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(url: str) -> IncrementalProcessingResult:
            async with semaphore:
                return await self.process_url_incremental(
                    url=url,
                    force_reprocess=force_reprocess,
                    **processing_kwargs
                )
        
        # Process all URLs concurrently
        tasks = [process_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception in incremental processing {urls[i]}: {result}")
                processed_results.append(IncrementalProcessingResult(
                    url=urls[i],
                    change_detection=ChangeDetectionResult(
                        url=urls[i],
                        change_type=ChangeType.UNCHANGED,
                        previous_snapshot=None,
                        current_snapshot=None,
                        changes_detected=[f"Processing exception: {str(result)}"],
                        confidence_score=0.0,
                        processing_required=False
                    )
                ))
            else:
                processed_results.append(result)
        
        # Log summary
        new_count = sum(1 for r in processed_results if r.change_detection.change_type == ChangeType.ADDED)
        modified_count = sum(1 for r in processed_results if r.change_detection.change_type == ChangeType.MODIFIED)
        unchanged_count = sum(1 for r in processed_results if r.change_detection.change_type == ChangeType.UNCHANGED)
        
        logger.info(f"Incremental batch processing completed: {new_count} new, "
                   f"{modified_count} modified, {unchanged_count} unchanged")
        
        return processed_results
    
    def _create_snapshot_from_result(self, processing_result: ProcessingResult) -> ContentSnapshot:
        """Create a ContentSnapshot from a ProcessingResult."""
        document = processing_result.document
        metadata = processing_result.metadata
        
        # Calculate hashes
        content_hash = document.get_content_hash()
        metadata_hash = hashlib.sha256(json.dumps(metadata.to_dict(), sort_keys=True).encode()).hexdigest()
        
        # Calculate screenshot hash if available
        screenshot_hash = None
        if document.screenshot_data:
            screenshot_hash = hashlib.sha256(document.screenshot_data).hexdigest()
        
        # Calculate DOM structure hash if available
        dom_structure_hash = None
        if document.dom_structure:
            dom_structure_hash = hashlib.sha256(
                json.dumps(document.dom_structure, sort_keys=True).encode()
            ).hexdigest()
        
        return ContentSnapshot(
            url=processing_result.url,
            content_hash=content_hash,
            content_length=len(document.text),
            page_title=metadata.page_title,
            last_modified=metadata.modified_date,
            extraction_timestamp=document.extraction_timestamp,
            metadata_hash=metadata_hash,
            screenshot_hash=screenshot_hash,
            dom_structure_hash=dom_structure_hash
        )
    
    def _update_stats(self, change_type: ChangeType, processing_time_ms: int):
        """Update processing statistics."""
        self._stats['total_processed'] += 1
        self._stats['total_processing_time_ms'] += processing_time_ms
        
        if change_type == ChangeType.ADDED:
            self._stats['new_content'] += 1
        elif change_type == ChangeType.MODIFIED:
            self._stats['modified_content'] += 1
        elif change_type == ChangeType.UNCHANGED:
            self._stats['unchanged_content'] += 1
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get incremental processing statistics."""
        stats = self._stats.copy()
        if stats['total_processed'] > 0:
            stats['average_processing_time_ms'] = stats['total_processing_time_ms'] / stats['total_processed']
            stats['change_rate'] = (stats['new_content'] + stats['modified_content']) / stats['total_processed']
        else:
            stats['average_processing_time_ms'] = 0.0
            stats['change_rate'] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self._stats = {
            'total_processed': 0,
            'new_content': 0,
            'modified_content': 0,
            'unchanged_content': 0,
            'processing_errors': 0,
            'total_processing_time_ms': 0
        }
    
    def cleanup_old_history(self, retention_days: int = 30) -> int:
        """Clean up old content history."""
        return self.history_manager.cleanup_old_snapshots(retention_days)
    
    def get_monitored_urls(self) -> List[str]:
        """Get list of monitored URLs."""
        return self.history_manager.get_monitored_urls()
    
    def get_url_history(self, url: str, limit: int = 10) -> List[ContentSnapshot]:
        """Get content history for a specific URL."""
        return self.history_manager.get_snapshots_history(url, limit)


class ContentMonitor:
    """
    Continuous content monitoring service.
    
    This class provides scheduled monitoring of web content with
    automatic incremental processing when changes are detected.
    """
    
    def __init__(self,
                 incremental_processor: IncrementalProcessor,
                 check_interval_minutes: int = 60,
                 max_concurrent_checks: int = 10):
        """
        Initialize content monitor.
        
        Args:
            incremental_processor: Incremental processor instance
            check_interval_minutes: Minutes between content checks
            max_concurrent_checks: Maximum concurrent URL checks
        """
        self.incremental_processor = incremental_processor
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.max_concurrent_checks = max_concurrent_checks
        
        self._monitored_urls: Set[str] = set()
        self._monitoring_status = MonitoringStatus.STOPPED
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_check: Optional[datetime] = None
    
    def add_url(self, url: str):
        """Add URL to monitoring list."""
        self._monitored_urls.add(url)
        logger.info(f"Added {url} to content monitoring")
    
    def remove_url(self, url: str):
        """Remove URL from monitoring list."""
        self._monitored_urls.discard(url)
        logger.info(f"Removed {url} from content monitoring")
    
    def get_monitored_urls(self) -> List[str]:
        """Get list of monitored URLs."""
        return list(self._monitored_urls)
    
    async def start_monitoring(self):
        """Start continuous content monitoring."""
        if self._monitoring_status == MonitoringStatus.ACTIVE:
            logger.warning("Content monitoring is already active")
            return
        
        self._monitoring_status = MonitoringStatus.ACTIVE
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Started content monitoring with {len(self._monitored_urls)} URLs")
    
    async def stop_monitoring(self):
        """Stop content monitoring."""
        if self._monitoring_status == MonitoringStatus.STOPPED:
            return
        
        self._monitoring_status = MonitoringStatus.STOPPED
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        
        logger.info("Stopped content monitoring")
    
    async def pause_monitoring(self):
        """Pause content monitoring."""
        if self._monitoring_status == MonitoringStatus.ACTIVE:
            self._monitoring_status = MonitoringStatus.PAUSED
            logger.info("Paused content monitoring")
    
    async def resume_monitoring(self):
        """Resume content monitoring."""
        if self._monitoring_status == MonitoringStatus.PAUSED:
            self._monitoring_status = MonitoringStatus.ACTIVE
            logger.info("Resumed content monitoring")
    
    async def check_all_urls(self) -> List[IncrementalProcessingResult]:
        """Manually trigger check of all monitored URLs."""
        if not self._monitored_urls:
            logger.warning("No URLs configured for monitoring")
            return []
        
        logger.info(f"Checking {len(self._monitored_urls)} monitored URLs")
        
        results = await self.incremental_processor.process_urls_incremental(
            urls=list(self._monitored_urls),
            max_concurrent=self.max_concurrent_checks
        )
        
        self._last_check = datetime.now(timezone.utc)
        
        # Log summary
        changed_count = sum(1 for r in results 
                          if r.change_detection.change_type in [ChangeType.ADDED, ChangeType.MODIFIED])
        logger.info(f"Content check completed: {changed_count}/{len(results)} URLs had changes")
        
        return results
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        logger.info("Content monitoring loop started")
        
        try:
            while self._monitoring_status in [MonitoringStatus.ACTIVE, MonitoringStatus.PAUSED]:
                if self._monitoring_status == MonitoringStatus.ACTIVE and self._monitored_urls:
                    try:
                        await self.check_all_urls()
                    except Exception as e:
                        logger.error(f"Error during content monitoring check: {e}")
                        self._monitoring_status = MonitoringStatus.ERROR
                        break
                
                # Wait for next check interval
                await asyncio.sleep(self.check_interval.total_seconds())
                
        except asyncio.CancelledError:
            logger.info("Content monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Content monitoring loop failed: {e}")
            self._monitoring_status = MonitoringStatus.ERROR
        finally:
            logger.info("Content monitoring loop ended")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            'status': self._monitoring_status.value,
            'monitored_urls_count': len(self._monitored_urls),
            'check_interval_minutes': self.check_interval.total_seconds() / 60,
            'last_check': self._last_check.isoformat() if self._last_check else None,
            'next_check': (self._last_check + self.check_interval).isoformat() if self._last_check else None
        }