"""
Monitoring and observability components for AgentCore browser tool integration.

This module provides comprehensive logging, metrics collection, error tracking,
and debugging utilities for AgentCore browser tool operations.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
from collections import defaultdict, deque
import threading
import weakref

from interfaces import BrowserResponse, BrowserData
from exceptions import AgentCoreBrowserError, BrowserErrorType


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class LogLevel(Enum):
    """Log levels for browser operations."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class OperationMetrics:
    """Metrics for a browser operation."""
    operation_id: str
    operation_type: str
    session_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    request_size: Optional[int] = None
    response_size: Optional[int] = None
    retry_count: int = 0
    recovery_attempts: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def complete(self, success: bool = True, error: Optional[Exception] = None):
        """Mark operation as complete."""
        if self.end_time is None:
            self.end_time = datetime.now(timezone.utc)
        if self.duration_ms is None:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        
        if error:
            if isinstance(error, AgentCoreBrowserError):
                self.error_type = error.error_type.value if error.error_type else type(error).__name__
            else:
                self.error_type = type(error).__name__
            self.error_message = str(error)


@dataclass
class PerformanceMetrics:
    """Performance metrics for browser operations."""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    operations_per_second: float = 0.0
    error_rate: float = 0.0
    retry_rate: float = 0.0
    recovery_rate: float = 0.0
    
    def update(self, operation: OperationMetrics):
        """Update metrics with new operation data."""
        self.total_operations += 1
        
        if operation.success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        if operation.duration_ms is not None:
            self.total_duration_ms += operation.duration_ms
            if self.min_duration_ms == float('inf'):
                self.min_duration_ms = operation.duration_ms
            else:
                self.min_duration_ms = min(self.min_duration_ms, operation.duration_ms)
            self.max_duration_ms = max(self.max_duration_ms, operation.duration_ms)
            self.average_duration_ms = self.total_duration_ms / self.total_operations
        
        self.error_rate = self.failed_operations / self.total_operations
        self.retry_rate = sum(1 for op in [operation] if op.retry_count > 0) / self.total_operations
        self.recovery_rate = sum(1 for op in [operation] if op.recovery_attempts > 0) / self.total_operations


class BrowserOperationLogger:
    """Specialized logger for browser operations with structured logging."""
    
    def __init__(self, name: str = "agentcore_browser", level: int = logging.INFO):
        """
        Initialize browser operation logger.
        
        Args:
            name: Logger name
            level: Logging level
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Create formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[%(session_id)s] [%(operation_id)s] %(operation_type)s - %(message)s'
        )
        
        # Add console handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_operation_start(self, 
                           operation_id: str,
                           operation_type: str,
                           session_id: Optional[str] = None,
                           details: Optional[Dict[str, Any]] = None):
        """Log the start of a browser operation."""
        extra = {
            'operation_id': operation_id,
            'operation_type': operation_type,
            'session_id': session_id or 'none'
        }
        
        message = f"Starting {operation_type}"
        if details:
            message += f" with details: {json.dumps(details, default=str)}"
        
        self.logger.info(message, extra=extra)
    
    def log_operation_success(self,
                             operation_id: str,
                             operation_type: str,
                             session_id: Optional[str] = None,
                             duration_ms: Optional[float] = None,
                             result_summary: Optional[Dict[str, Any]] = None):
        """Log successful completion of a browser operation."""
        extra = {
            'operation_id': operation_id,
            'operation_type': operation_type,
            'session_id': session_id or 'none'
        }
        
        message = f"Completed {operation_type} successfully"
        if duration_ms is not None:
            message += f" in {duration_ms:.2f}ms"
        if result_summary:
            message += f" - {json.dumps(result_summary, default=str)}"
        
        self.logger.info(message, extra=extra)
    
    def log_operation_error(self,
                           operation_id: str,
                           operation_type: str,
                           error: Exception,
                           session_id: Optional[str] = None,
                           duration_ms: Optional[float] = None,
                           retry_count: int = 0):
        """Log error during browser operation."""
        extra = {
            'operation_id': operation_id,
            'operation_type': operation_type,
            'session_id': session_id or 'none'
        }
        
        message = f"Failed {operation_type}"
        if duration_ms is not None:
            message += f" after {duration_ms:.2f}ms"
        if retry_count > 0:
            message += f" (retry {retry_count})"
        message += f" - {type(error).__name__}: {str(error)}"
        
        self.logger.error(message, extra=extra, exc_info=True)
    
    def log_api_call(self,
                    method: str,
                    endpoint: str,
                    session_id: Optional[str] = None,
                    request_size: Optional[int] = None,
                    response_code: Optional[int] = None,
                    response_size: Optional[int] = None,
                    duration_ms: Optional[float] = None):
        """Log AgentCore API call details."""
        extra = {
            'operation_id': 'api_call',
            'operation_type': 'api_request',
            'session_id': session_id or 'none'
        }
        
        message = f"API {method} {endpoint}"
        if response_code:
            message += f" -> {response_code}"
        if duration_ms is not None:
            message += f" ({duration_ms:.2f}ms)"
        if request_size and response_size:
            message += f" [{request_size}B -> {response_size}B]"
        
        level = logging.INFO if (response_code or 0) < 400 else logging.ERROR
        self.logger.log(level, message, extra=extra)
    
    def log_debug_info(self,
                      operation_id: str,
                      operation_type: str,
                      debug_data: Dict[str, Any],
                      session_id: Optional[str] = None):
        """Log debug information for troubleshooting."""
        extra = {
            'operation_id': operation_id,
            'operation_type': operation_type,
            'session_id': session_id or 'none'
        }
        
        message = f"Debug info for {operation_type}: {json.dumps(debug_data, default=str)}"
        self.logger.debug(message, extra=extra)


class MetricsCollector:
    """Collects and aggregates metrics for browser operations."""
    
    def __init__(self, max_history: int = 10000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of operations to keep in history
        """
        self.max_history = max_history
        self._operations: deque = deque(maxlen=max_history)
        self._metrics_by_type: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self._metrics_by_session: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def record_operation(self, operation: OperationMetrics):
        """Record a completed operation."""
        with self._lock:
            self._operations.append(operation)
            
            # Update type-specific metrics
            self._metrics_by_type[operation.operation_type].update(operation)
            
            # Update session-specific metrics
            if operation.session_id:
                self._metrics_by_session[operation.session_id].update(operation)
            
            # Update error counts
            if not operation.success and operation.error_type:
                # Convert error type to lowercase for consistency
                error_key = operation.error_type.lower().replace('error', '')
                if not error_key:
                    error_key = operation.error_type
                self._error_counts[error_key] += 1
    
    def get_overall_metrics(self) -> PerformanceMetrics:
        """Get overall performance metrics."""
        with self._lock:
            overall = PerformanceMetrics()
            for operation in self._operations:
                overall.update(operation)
            return overall
    
    def get_metrics_by_type(self, operation_type: str) -> PerformanceMetrics:
        """Get metrics for specific operation type."""
        with self._lock:
            return self._metrics_by_type.get(operation_type, PerformanceMetrics())
    
    def get_metrics_by_session(self, session_id: str) -> PerformanceMetrics:
        """Get metrics for specific session."""
        with self._lock:
            return self._metrics_by_session.get(session_id, PerformanceMetrics())
    
    def get_error_summary(self) -> Dict[str, int]:
        """Get summary of error counts by type."""
        with self._lock:
            return dict(self._error_counts)
    
    def get_recent_operations(self, count: int = 100) -> List[OperationMetrics]:
        """Get most recent operations."""
        with self._lock:
            return list(self._operations)[-count:]
    
    def clear_metrics(self):
        """Clear all collected metrics."""
        with self._lock:
            self._operations.clear()
            self._metrics_by_type.clear()
            self._metrics_by_session.clear()
            self._error_counts.clear()


class ErrorTracker:
    """Tracks and analyzes errors for alerting and debugging."""
    
    def __init__(self, alert_threshold: int = 5, time_window_minutes: int = 5):
        """
        Initialize error tracker.
        
        Args:
            alert_threshold: Number of errors to trigger alert
            time_window_minutes: Time window for error rate calculation
        """
        self.alert_threshold = alert_threshold
        self.time_window = timedelta(minutes=time_window_minutes)
        self._errors: deque = deque()
        self._alert_callbacks: List[Callable] = []
        self._lock = threading.Lock()
    
    def record_error(self, 
                    error: Exception,
                    operation_type: str,
                    session_id: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None):
        """Record an error occurrence."""
        error_record = {
            'timestamp': datetime.now(timezone.utc),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'operation_type': operation_type,
            'session_id': session_id,
            'context': context or {}
        }
        
        with self._lock:
            self._errors.append(error_record)
            self._cleanup_old_errors()
            
            # Check if alert threshold is reached
            recent_errors = self._get_recent_errors()
            if len(recent_errors) >= self.alert_threshold:
                self._trigger_alerts(recent_errors)
    
    def _cleanup_old_errors(self):
        """Remove errors outside the time window."""
        cutoff_time = datetime.now(timezone.utc) - self.time_window
        while self._errors and self._errors[0]['timestamp'] < cutoff_time:
            self._errors.popleft()
    
    def _get_recent_errors(self) -> List[Dict[str, Any]]:
        """Get errors within the time window."""
        cutoff_time = datetime.now(timezone.utc) - self.time_window
        return [error for error in self._errors if error['timestamp'] >= cutoff_time]
    
    def _trigger_alerts(self, recent_errors: List[Dict[str, Any]]):
        """Trigger alert callbacks for high error rate."""
        for callback in self._alert_callbacks:
            try:
                callback(recent_errors)
            except Exception as e:
                logging.error(f"Error in alert callback: {e}")
    
    def add_alert_callback(self, callback: Callable[[List[Dict[str, Any]]], None]):
        """Add callback to be called when error threshold is reached."""
        self._alert_callbacks.append(callback)
    
    def get_error_rate(self) -> float:
        """Get current error rate (errors per minute)."""
        recent_errors = self._get_recent_errors()
        return len(recent_errors) / self.time_window.total_seconds() * 60
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors."""
        with self._lock:
            recent_errors = self._get_recent_errors()
            error_types = defaultdict(int)
            operation_types = defaultdict(int)
            
            for error in recent_errors:
                error_types[error['error_type']] += 1
                operation_types[error['operation_type']] += 1
            
            # Calculate error rate without additional locking
            error_rate = len(recent_errors) / self.time_window.total_seconds() * 60
            
            return {
                'total_errors': len(recent_errors),
                'error_rate_per_minute': error_rate,
                'error_types': dict(error_types),
                'operation_types': dict(operation_types),
                'time_window_minutes': self.time_window.total_seconds() / 60
            }


class DebugUtilities:
    """Debugging utilities using AgentCore browser tool capabilities."""
    
    def __init__(self, browser_client):
        """
        Initialize debug utilities.
        
        Args:
            browser_client: AgentCore browser client instance
        """
        self.browser_client = browser_client
        self.logger = BrowserOperationLogger("debug_utilities")
    
    async def capture_debug_snapshot(self, 
                                   operation_id: str,
                                   session_id: Optional[str] = None,
                                   include_screenshot: bool = True,
                                   include_page_source: bool = True,
                                   include_console_logs: bool = True) -> Dict[str, Any]:
        """
        Capture comprehensive debug snapshot for failed operations.
        
        Args:
            operation_id: ID of the operation being debugged
            session_id: Browser session ID
            include_screenshot: Whether to capture screenshot
            include_page_source: Whether to capture page source
            include_console_logs: Whether to capture console logs
            
        Returns:
            Debug snapshot data
        """
        snapshot = {
            'operation_id': operation_id,
            'session_id': session_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'debug_data': {}
        }
        
        try:
            # Capture screenshot if requested
            if include_screenshot:
                try:
                    screenshot_response = await self.browser_client.take_screenshot(full_page=True)
                    if screenshot_response.success:
                        snapshot['debug_data']['screenshot'] = {
                            'data': screenshot_response.data.get('screenshot_data'),
                            'format': screenshot_response.data.get('format', 'png'),
                            'size': screenshot_response.data.get('size', {})
                        }
                except Exception as e:
                    snapshot['debug_data']['screenshot_error'] = str(e)
            
            # Capture page source if requested
            if include_page_source:
                try:
                    # Use text extraction to get page content
                    text_response = await self.browser_client.extract_text()
                    if text_response.success:
                        snapshot['debug_data']['page_content'] = {
                            'text': text_response.data.get('text', ''),
                            'length': len(text_response.data.get('text', '')),
                            'element_count': text_response.data.get('element_count', 0)
                        }
                except Exception as e:
                    snapshot['debug_data']['page_content_error'] = str(e)
            
            # Get current page info
            try:
                page_info = await self.browser_client.get_page_info()
                if page_info.success:
                    snapshot['debug_data']['page_info'] = page_info.data
            except Exception as e:
                snapshot['debug_data']['page_info_error'] = str(e)
            
            # Log debug snapshot creation
            self.logger.log_debug_info(
                operation_id=operation_id,
                operation_type="debug_snapshot",
                debug_data={
                    'snapshot_size': len(str(snapshot)),
                    'components_captured': list(snapshot['debug_data'].keys())
                },
                session_id=session_id
            )
            
        except Exception as e:
            snapshot['capture_error'] = str(e)
            self.logger.log_operation_error(
                operation_id=operation_id,
                operation_type="debug_snapshot",
                error=e,
                session_id=session_id
            )
        
        return snapshot
    
    async def analyze_operation_failure(self,
                                      operation_metrics: OperationMetrics,
                                      capture_snapshot: bool = True) -> Dict[str, Any]:
        """
        Analyze a failed operation and provide debugging information.
        
        Args:
            operation_metrics: Metrics from the failed operation
            capture_snapshot: Whether to capture debug snapshot
            
        Returns:
            Analysis results with debugging information
        """
        analysis = {
            'operation_id': operation_metrics.operation_id,
            'operation_type': operation_metrics.operation_type,
            'session_id': operation_metrics.session_id,
            'failure_analysis': {},
            'recommendations': []
        }
        
        # Analyze error type and provide recommendations
        if operation_metrics.error_type:
            error_type = operation_metrics.error_type.lower()
            
            if 'timeout' in error_type:
                analysis['failure_analysis']['likely_cause'] = 'Operation timeout'
                analysis['recommendations'].extend([
                    'Increase timeout value',
                    'Check network connectivity',
                    'Verify page loading performance'
                ])
            
            elif 'element_not_found' in error_type:
                analysis['failure_analysis']['likely_cause'] = 'Element not found'
                analysis['recommendations'].extend([
                    'Verify element selector accuracy',
                    'Check if page has loaded completely',
                    'Consider waiting for dynamic content'
                ])
            
            elif 'session' in error_type:
                analysis['failure_analysis']['likely_cause'] = 'Session management issue'
                analysis['recommendations'].extend([
                    'Recreate browser session',
                    'Check session timeout settings',
                    'Verify authentication status'
                ])
            
            elif 'network' in error_type or 'service' in error_type:
                analysis['failure_analysis']['likely_cause'] = 'Network or service issue'
                analysis['recommendations'].extend([
                    'Retry operation with backoff',
                    'Check AgentCore service status',
                    'Verify network connectivity'
                ])
        
        # Analyze operation duration
        if operation_metrics.duration_ms:
            if operation_metrics.duration_ms > 30000:  # 30 seconds
                analysis['failure_analysis']['performance_issue'] = 'Operation took unusually long'
                analysis['recommendations'].append('Consider optimizing operation or increasing timeout')
        
        # Analyze retry patterns
        if operation_metrics.retry_count > 0:
            analysis['failure_analysis']['retry_pattern'] = f'Failed after {operation_metrics.retry_count} retries'
            if operation_metrics.retry_count >= 3:
                analysis['recommendations'].append('Consider alternative approach or manual intervention')
        
        # Capture debug snapshot if requested
        if capture_snapshot and operation_metrics.session_id:
            try:
                snapshot = await self.capture_debug_snapshot(
                    operation_id=operation_metrics.operation_id,
                    session_id=operation_metrics.session_id
                )
                analysis['debug_snapshot'] = snapshot
            except Exception as e:
                analysis['debug_snapshot_error'] = str(e)
        
        return analysis


class OperationMonitor:
    """Context manager for monitoring browser operations."""
    
    def __init__(self,
                 operation_type: str,
                 session_id: Optional[str] = None,
                 logger: Optional[BrowserOperationLogger] = None,
                 metrics_collector: Optional[MetricsCollector] = None,
                 error_tracker: Optional[ErrorTracker] = None):
        """
        Initialize operation monitor.
        
        Args:
            operation_type: Type of operation being monitored
            session_id: Browser session ID
            logger: Logger instance
            metrics_collector: Metrics collector instance
            error_tracker: Error tracker instance
        """
        self.operation_id = str(uuid.uuid4())
        self.operation_type = operation_type
        self.session_id = session_id
        self.logger = logger or BrowserOperationLogger()
        self.metrics_collector = metrics_collector
        self.error_tracker = error_tracker
        
        self.metrics = OperationMetrics(
            operation_id=self.operation_id,
            operation_type=operation_type,
            session_id=session_id,
            start_time=datetime.now(timezone.utc)
        )
        
        self._context_data: Dict[str, Any] = {}
    
    def __enter__(self):
        """Enter monitoring context."""
        self.logger.log_operation_start(
            operation_id=self.operation_id,
            operation_type=self.operation_type,
            session_id=self.session_id
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit monitoring context."""
        success = exc_type is None
        error = exc_val if exc_type else None
        
        # Complete metrics
        self.metrics.complete(success=success, error=error)
        
        # Log operation completion
        if success:
            self.logger.log_operation_success(
                operation_id=self.operation_id,
                operation_type=self.operation_type,
                session_id=self.session_id,
                duration_ms=self.metrics.duration_ms
            )
        else:
            self.logger.log_operation_error(
                operation_id=self.operation_id,
                operation_type=self.operation_type,
                error=error,
                session_id=self.session_id,
                duration_ms=self.metrics.duration_ms
            )
        
        # Record metrics
        if self.metrics_collector:
            self.metrics_collector.record_operation(self.metrics)
        
        # Track errors
        if not success and error and self.error_tracker:
            self.error_tracker.record_error(
                error=error,
                operation_type=self.operation_type,
                session_id=self.session_id,
                context=self._context_data
            )
    
    def add_context(self, key: str, value: Any):
        """Add context data to the operation."""
        self._context_data[key] = value
        self.metrics.metadata[key] = value
    
    def set_request_size(self, size: int):
        """Set request size for the operation."""
        self.metrics.request_size = size
    
    def set_response_size(self, size: int):
        """Set response size for the operation."""
        self.metrics.response_size = size
    
    def increment_retry_count(self):
        """Increment retry count for the operation."""
        self.metrics.retry_count += 1
    
    def increment_recovery_attempts(self):
        """Increment recovery attempts for the operation."""
        self.metrics.recovery_attempts += 1


@asynccontextmanager
async def monitor_async_operation(operation_type: str,
                                session_id: Optional[str] = None,
                                logger: Optional[BrowserOperationLogger] = None,
                                metrics_collector: Optional[MetricsCollector] = None,
                                error_tracker: Optional[ErrorTracker] = None):
    """
    Async context manager for monitoring browser operations.
    
    Args:
        operation_type: Type of operation being monitored
        session_id: Browser session ID
        logger: Logger instance
        metrics_collector: Metrics collector instance
        error_tracker: Error tracker instance
    
    Yields:
        OperationMonitor instance
    """
    monitor = OperationMonitor(
        operation_type=operation_type,
        session_id=session_id,
        logger=logger,
        metrics_collector=metrics_collector,
        error_tracker=error_tracker
    )
    
    try:
        monitor.logger.log_operation_start(
            operation_id=monitor.operation_id,
            operation_type=monitor.operation_type,
            session_id=monitor.session_id
        )
        yield monitor
        
        # Mark as successful if no exception
        monitor.metrics.complete(success=True)
        monitor.logger.log_operation_success(
            operation_id=monitor.operation_id,
            operation_type=monitor.operation_type,
            session_id=monitor.session_id,
            duration_ms=monitor.metrics.duration_ms
        )
        
    except Exception as error:
        # Mark as failed
        monitor.metrics.complete(success=False, error=error)
        monitor.logger.log_operation_error(
            operation_id=monitor.operation_id,
            operation_type=monitor.operation_type,
            error=error,
            session_id=monitor.session_id,
            duration_ms=monitor.metrics.duration_ms
        )
        
        # Track error
        if monitor.error_tracker:
            monitor.error_tracker.record_error(
                error=error,
                operation_type=monitor.operation_type,
                session_id=monitor.session_id,
                context=monitor._context_data
            )
        
        raise
    
    finally:
        # Record metrics
        if monitor.metrics_collector:
            monitor.metrics_collector.record_operation(monitor.metrics)