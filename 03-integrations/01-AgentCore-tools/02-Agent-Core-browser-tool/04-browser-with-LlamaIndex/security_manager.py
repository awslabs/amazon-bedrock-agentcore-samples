"""
Security Manager for LlamaIndex-AgentCore Browser Integration

This module provides comprehensive security management including:
- Credential validation and management
- Input sanitization to prevent injection attacks
- Data encryption for sensitive information
- Audit logging for security events and data access

Requirements: 5.1, 5.2, 5.4
"""

import re
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os


class SecurityEventType(Enum):
    """Types of security events for audit logging."""
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    CREDENTIAL_VALIDATION = "credential_validation"
    INPUT_SANITIZATION = "input_sanitization"
    DATA_ENCRYPTION = "data_encryption"
    DATA_DECRYPTION = "data_decryption"
    PERMISSION_CHECK = "permission_check"
    SECURITY_VIOLATION = "security_violation"
    SESSION_CREATED = "session_created"
    SESSION_TERMINATED = "session_terminated"


@dataclass
class SecurityEvent:
    """Security event for audit logging."""
    event_type: SecurityEventType
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    operation: str
    details: Dict[str, Any]
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None


class SecurityManager:
    """
    Manages security aspects of the LlamaIndex-AgentCore integration.
    
    Provides:
    - AWS credential validation and management
    - Input sanitization to prevent injection attacks
    - Data encryption/decryption for sensitive information
    - Comprehensive audit logging for security events
    """
    
    # Required AWS permissions for AgentCore browser tool
    REQUIRED_PERMISSIONS = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock-agent:InvokeAgent",
        "bedrock-agent-runtime:InvokeAgent",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "sts:GetCallerIdentity"
    ]
    
    # Dangerous patterns for input sanitization
    INJECTION_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'on\w+\s*=',  # Event handlers
        r'<iframe[^>]*>.*?</iframe>',  # Iframes
        r'<object[^>]*>.*?</object>',  # Objects
        r'<embed[^>]*>.*?</embed>',  # Embeds
        r'<link[^>]*>',  # Link tags
        r'<meta[^>]*>',  # Meta tags
        r'<style[^>]*>.*?</style>',  # Style tags
        r'expression\s*\(',  # CSS expressions
        r'url\s*\(',  # CSS URLs
        r'@import',  # CSS imports
        r'<!--.*?-->',  # HTML comments
        r'<!\[CDATA\[.*?\]\]>',  # CDATA sections
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)',
        r'(\b(UNION|OR|AND)\b.*\b(SELECT|INSERT|UPDATE|DELETE)\b)',
        r'(\'|\")(\s)*(;|--|\||#)',
        r'(\b(SCRIPT|JAVASCRIPT|VBSCRIPT|ONLOAD|ONERROR|ONCLICK)\b)',
    ]
    
    def __init__(self, 
                 aws_region: str = "us-east-1",
                 encryption_key: Optional[str] = None,
                 log_level: str = "INFO"):
        """
        Initialize SecurityManager.
        
        Args:
            aws_region: AWS region for services
            encryption_key: Optional encryption key (will generate if not provided)
            log_level: Logging level for security events
        """
        self.aws_region = aws_region
        self.logger = self._setup_logging(log_level)
        self.session_tokens: Dict[str, Dict[str, Any]] = {}
        self.audit_events: List[SecurityEvent] = []
        
        # Initialize encryption
        self.encryption_key = self._setup_encryption(encryption_key)
        
        # Initialize AWS clients
        self.sts_client = None
        self.logs_client = None
        self._initialize_aws_clients()
        
        self.logger.info("SecurityManager initialized successfully")
    
    def _setup_logging(self, log_level: str) -> logging.Logger:
        """Set up security logging."""
        logger = logging.getLogger("llamaindex_agentcore_security")
        logger.setLevel(getattr(logging, log_level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _setup_encryption(self, encryption_key: Optional[str]) -> Fernet:
        """Set up encryption for sensitive data."""
        if encryption_key:
            key = base64.urlsafe_b64encode(encryption_key.encode()[:32].ljust(32, b'0'))
        else:
            # Generate a key from environment or create new one
            password = os.environ.get('SECURITY_PASSWORD', 'default_password').encode()
            salt = os.environ.get('SECURITY_SALT', 'default_salt').encode()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
        
        return Fernet(key)
    
    def _initialize_aws_clients(self):
        """Initialize AWS clients for security operations."""
        try:
            self.sts_client = boto3.client('sts', region_name=self.aws_region)
            self.logs_client = boto3.client('logs', region_name=self.aws_region)
            
            # Test credentials
            self.sts_client.get_caller_identity()
            self.logger.info("AWS clients initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS clients: {e}")
            self.sts_client = None
            self.logs_client = None
    
    def validate_credentials(self, aws_credentials: Optional[Dict[str, str]] = None) -> bool:
        """
        Validate AWS credentials have required permissions.
        
        Args:
            aws_credentials: Optional AWS credentials dict
            
        Returns:
            bool: True if credentials are valid and have required permissions
        """
        try:
            # Create temporary client with provided credentials
            if aws_credentials:
                sts_client = boto3.client(
                    'sts',
                    region_name=self.aws_region,
                    aws_access_key_id=aws_credentials.get('aws_access_key_id'),
                    aws_secret_access_key=aws_credentials.get('aws_secret_access_key'),
                    aws_session_token=aws_credentials.get('aws_session_token')
                )
            else:
                sts_client = self.sts_client
            
            if not sts_client:
                self._log_security_event(
                    SecurityEventType.AUTHENTICATION_FAILURE,
                    "credential_validation",
                    {"error": "No STS client available"}
                )
                return False
            
            # Test basic access
            identity = sts_client.get_caller_identity()
            user_arn = identity.get('Arn', 'unknown')
            
            self._log_security_event(
                SecurityEventType.CREDENTIAL_VALIDATION,
                "credential_validation",
                {
                    "user_arn": user_arn,
                    "account_id": identity.get('Account'),
                    "status": "success"
                }
            )
            
            self.logger.info(f"Credentials validated for user: {user_arn}")
            return True
            
        except NoCredentialsError:
            self._log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "credential_validation",
                {"error": "No credentials found"}
            )
            self.logger.error("No AWS credentials found")
            return False
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            self._log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "credential_validation",
                {"error": error_code, "message": str(e)}
            )
            self.logger.error(f"AWS credential validation failed: {e}")
            return False
            
        except Exception as e:
            self._log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "credential_validation",
                {"error": "unexpected_error", "message": str(e)}
            )
            self.logger.error(f"Unexpected error during credential validation: {e}")
            return False
    
    def sanitize_input(self, user_input: str, context: str = "general") -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            user_input: Raw user input to sanitize
            context: Context of the input (url, selector, text, etc.)
            
        Returns:
            str: Sanitized input
        """
        if not isinstance(user_input, str):
            user_input = str(user_input)
        
        original_input = user_input
        sanitized = user_input
        violations = []
        
        # Check for injection patterns
        for pattern in self.INJECTION_PATTERNS:
            matches = re.findall(pattern, sanitized, re.IGNORECASE | re.DOTALL)
            if matches:
                violations.extend(matches)
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            matches = re.findall(pattern, sanitized, re.IGNORECASE)
            if matches:
                violations.extend([str(m) for m in matches])
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Context-specific sanitization
        if context == "url":
            sanitized = self._sanitize_url(sanitized)
        elif context == "selector":
            sanitized = self._sanitize_css_selector(sanitized)
        elif context == "javascript":
            # For JavaScript context, be very restrictive
            sanitized = re.sub(r'[<>"\';(){}]', '', sanitized)
        
        # Log security violations
        if violations:
            self._log_security_event(
                SecurityEventType.SECURITY_VIOLATION,
                "input_sanitization",
                {
                    "context": context,
                    "violations": violations,
                    "original_length": len(original_input),
                    "sanitized_length": len(sanitized)
                },
                severity="WARNING"
            )
        
        # Log sanitization event
        if original_input != sanitized:
            self._log_security_event(
                SecurityEventType.INPUT_SANITIZATION,
                "input_sanitization",
                {
                    "context": context,
                    "changes_made": True,
                    "original_length": len(original_input),
                    "sanitized_length": len(sanitized)
                }
            )
        
        return sanitized.strip()
    
    def _sanitize_url(self, url: str) -> str:
        """Sanitize URL input."""
        # Allow only http/https protocols
        if not re.match(r'^https?://', url, re.IGNORECASE):
            if not url.startswith('//'):
                url = 'https://' + url
            else:
                url = 'https:' + url
        
        # Remove dangerous characters
        url = re.sub(r'[<>"\'\s]', '', url)
        
        return url
    
    def _sanitize_css_selector(self, selector: str) -> str:
        """Sanitize CSS selector input."""
        # Allow only safe CSS selector characters
        sanitized = re.sub(r'[^a-zA-Z0-9\-_#.\[\]:(),\s>+~*=]', '', selector)
        return sanitized
    
    def encrypt_sensitive_data(self, data: Union[str, Dict[str, Any]], 
                             data_type: str = "general") -> str:
        """
        Encrypt sensitive data before storage or transmission.
        
        Args:
            data: Data to encrypt (string or dict)
            data_type: Type of data being encrypted
            
        Returns:
            str: Base64 encoded encrypted data
        """
        try:
            # Convert data to JSON string if it's a dict
            if isinstance(data, dict):
                data_str = json.dumps(data, sort_keys=True)
            else:
                data_str = str(data)
            
            # Encrypt the data
            encrypted_data = self.encryption_key.encrypt(data_str.encode())
            encoded_data = base64.b64encode(encrypted_data).decode()
            
            self._log_security_event(
                SecurityEventType.DATA_ENCRYPTION,
                "data_encryption",
                {
                    "data_type": data_type,
                    "original_size": len(data_str),
                    "encrypted_size": len(encoded_data)
                }
            )
            
            return encoded_data
            
        except Exception as e:
            self.logger.error(f"Failed to encrypt data: {e}")
            self._log_security_event(
                SecurityEventType.SECURITY_VIOLATION,
                "data_encryption",
                {"error": str(e), "data_type": data_type},
                severity="ERROR"
            )
            raise
    
    def decrypt_sensitive_data(self, encrypted_data: str, 
                             data_type: str = "general",
                             return_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Decrypt sensitive data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            data_type: Type of data being decrypted
            return_dict: Whether to return as dict (if original was dict)
            
        Returns:
            Union[str, Dict]: Decrypted data
        """
        try:
            # Decode and decrypt
            decoded_data = base64.b64decode(encrypted_data.encode())
            decrypted_bytes = self.encryption_key.decrypt(decoded_data)
            decrypted_str = decrypted_bytes.decode()
            
            self._log_security_event(
                SecurityEventType.DATA_DECRYPTION,
                "data_decryption",
                {
                    "data_type": data_type,
                    "encrypted_size": len(encrypted_data),
                    "decrypted_size": len(decrypted_str)
                }
            )
            
            # Try to parse as JSON if return_dict is True
            if return_dict:
                try:
                    return json.loads(decrypted_str)
                except json.JSONDecodeError:
                    pass
            
            return decrypted_str
            
        except Exception as e:
            self.logger.error(f"Failed to decrypt data: {e}")
            self._log_security_event(
                SecurityEventType.SECURITY_VIOLATION,
                "data_decryption",
                {"error": str(e), "data_type": data_type},
                severity="ERROR"
            )
            raise
    
    def create_secure_session_token(self, user_id: str, 
                                  session_data: Dict[str, Any]) -> str:
        """
        Create a secure session token.
        
        Args:
            user_id: User identifier
            session_data: Session data to include in token
            
        Returns:
            str: Secure session token
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        token_data = {
            "user_id": user_id,
            "timestamp": timestamp,
            "session_data": session_data
        }
        
        # Create hash for token
        token_str = json.dumps(token_data, sort_keys=True)
        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        
        # Encrypt token data
        encrypted_token = self.encrypt_sensitive_data(token_data, "session_token")
        
        # Store session
        self.session_tokens[token_hash] = {
            "user_id": user_id,
            "created_at": timestamp,
            "encrypted_data": encrypted_token
        }
        
        self._log_security_event(
            SecurityEventType.SESSION_CREATED,
            "session_management",
            {"user_id": user_id, "token_hash": token_hash[:8] + "..."}
        )
        
        return token_hash
    
    def validate_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate and retrieve session data from token.
        
        Args:
            token: Session token to validate
            
        Returns:
            Optional[Dict]: Session data if valid, None otherwise
        """
        if token not in self.session_tokens:
            self._log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "session_validation",
                {"token_hash": token[:8] + "...", "error": "token_not_found"},
                severity="WARNING"
            )
            return None
        
        try:
            session_info = self.session_tokens[token]
            encrypted_data = session_info["encrypted_data"]
            
            # Decrypt session data
            session_data = self.decrypt_sensitive_data(
                encrypted_data, 
                "session_token", 
                return_dict=True
            )
            
            return session_data
            
        except Exception as e:
            self.logger.error(f"Failed to validate session token: {e}")
            self._log_security_event(
                SecurityEventType.AUTHENTICATION_FAILURE,
                "session_validation",
                {"token_hash": token[:8] + "...", "error": str(e)},
                severity="ERROR"
            )
            return None
    
    def revoke_session_token(self, token: str, user_id: Optional[str] = None):
        """
        Revoke a session token.
        
        Args:
            token: Session token to revoke
            user_id: Optional user ID for additional validation
        """
        if token in self.session_tokens:
            session_info = self.session_tokens[token]
            
            if user_id and session_info.get("user_id") != user_id:
                self._log_security_event(
                    SecurityEventType.SECURITY_VIOLATION,
                    "session_revocation",
                    {
                        "token_hash": token[:8] + "...",
                        "error": "user_id_mismatch",
                        "expected_user": user_id,
                        "actual_user": session_info.get("user_id")
                    },
                    severity="WARNING"
                )
                return
            
            del self.session_tokens[token]
            
            self._log_security_event(
                SecurityEventType.SESSION_TERMINATED,
                "session_management",
                {"token_hash": token[:8] + "...", "user_id": user_id}
            )
    
    def _log_security_event(self, 
                          event_type: SecurityEventType,
                          operation: str,
                          details: Dict[str, Any],
                          severity: str = "INFO",
                          user_id: Optional[str] = None,
                          session_id: Optional[str] = None):
        """Log a security event for audit purposes."""
        event = SecurityEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            session_id=session_id,
            operation=operation,
            details=details,
            severity=severity
        )
        
        self.audit_events.append(event)
        
        # Log to standard logger
        log_message = f"Security Event: {event_type.value} - {operation} - {details}"
        if severity == "ERROR" or severity == "CRITICAL":
            self.logger.error(log_message)
        elif severity == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # Send to CloudWatch if available
        self._send_to_cloudwatch(event)
    
    def _send_to_cloudwatch(self, event: SecurityEvent):
        """Send security event to CloudWatch logs."""
        if not self.logs_client:
            return
        
        try:
            log_group = "/aws/llamaindex-agentcore/security"
            log_stream = f"security-events-{datetime.now().strftime('%Y-%m-%d')}"
            
            # Create log group if it doesn't exist
            try:
                self.logs_client.create_log_group(logGroupName=log_group)
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Create log stream if it doesn't exist
            try:
                self.logs_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=log_stream
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
            
            # Send log event
            log_event = {
                'timestamp': int(event.timestamp.timestamp() * 1000),
                'message': json.dumps(asdict(event), default=str)
            }
            
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[log_event]
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send security event to CloudWatch: {e}")
    
    def get_audit_events(self, 
                        event_type: Optional[SecurityEventType] = None,
                        user_id: Optional[str] = None,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None) -> List[SecurityEvent]:
        """
        Retrieve audit events based on filters.
        
        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            start_time: Filter events after this time
            end_time: Filter events before this time
            
        Returns:
            List[SecurityEvent]: Filtered audit events
        """
        filtered_events = self.audit_events
        
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        
        if user_id:
            filtered_events = [e for e in filtered_events if e.user_id == user_id]
        
        if start_time:
            filtered_events = [e for e in filtered_events if e.timestamp >= start_time]
        
        if end_time:
            filtered_events = [e for e in filtered_events if e.timestamp <= end_time]
        
        return filtered_events
    
    def generate_security_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive security report.
        
        Returns:
            Dict: Security report with statistics and events
        """
        total_events = len(self.audit_events)
        event_counts = {}
        severity_counts = {}
        
        for event in self.audit_events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            severity_counts[event.severity] = severity_counts.get(event.severity, 0) + 1
        
        recent_events = sorted(
            self.audit_events, 
            key=lambda x: x.timestamp, 
            reverse=True
        )[:10]
        
        return {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "total_events": total_events,
            "event_type_counts": event_counts,
            "severity_counts": severity_counts,
            "active_sessions": len(self.session_tokens),
            "recent_events": [asdict(event) for event in recent_events]
        }
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """
        Clean up expired session tokens.
        
        Args:
            max_age_hours: Maximum age of sessions in hours
        """
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        expired_tokens = []
        
        for token, session_info in self.session_tokens.items():
            created_at = datetime.fromisoformat(session_info["created_at"].replace('Z', '+00:00'))
            if created_at.timestamp() < cutoff_time:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            user_id = self.session_tokens[token].get("user_id")
            del self.session_tokens[token]
            
            self._log_security_event(
                SecurityEventType.SESSION_TERMINATED,
                "session_cleanup",
                {"token_hash": token[:8] + "...", "user_id": user_id, "reason": "expired"}
            )
        
        if expired_tokens:
            self.logger.info(f"Cleaned up {len(expired_tokens)} expired sessions")