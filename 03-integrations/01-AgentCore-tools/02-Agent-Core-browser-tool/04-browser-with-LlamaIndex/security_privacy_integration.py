"""
Security and Privacy Integration Module

This module provides a unified interface for security and privacy management
in the LlamaIndex-AgentCore browser integration.

Combines SecurityManager and PrivacyManager functionality for comprehensive
data protection and compliance.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union

from security_manager import SecurityManager, SecurityEventType
from privacy_manager import PrivacyManager, PIIType, DataCategory, PIIDetection


class SecurityPrivacyManager:
    """
    Unified security and privacy manager for LlamaIndex-AgentCore integration.
    
    Provides comprehensive data protection by combining:
    - Security management (authentication, encryption, audit logging)
    - Privacy management (PII detection, data minimization, compliance)
    """
    
    def __init__(self,
                 aws_region: str = "us-east-1",
                 encryption_key: Optional[str] = None,
                 log_level: str = "INFO",
                 custom_pii_patterns: Optional[Dict] = None,
                 retention_policies: Optional[Dict] = None):
        """
        Initialize unified security and privacy manager.
        
        Args:
            aws_region: AWS region for services
            encryption_key: Optional encryption key
            log_level: Logging level
            custom_pii_patterns: Custom PII detection patterns
            retention_policies: Custom data retention policies
        """
        self.logger = self._setup_logging(log_level)
        
        # Initialize security manager
        self.security_manager = SecurityManager(
            aws_region=aws_region,
            encryption_key=encryption_key,
            log_level=log_level
        )
        
        # Initialize privacy manager
        self.privacy_manager = PrivacyManager(
            aws_region=aws_region,
            log_level=log_level,
            custom_pii_patterns=custom_pii_patterns,
            retention_policies=retention_policies
        )
        
        self.logger.info("SecurityPrivacyManager initialized successfully")
    
    def _setup_logging(self, log_level: str) -> logging.Logger:
        """Set up unified logging."""
        logger = logging.getLogger("llamaindex_agentcore_security_privacy")
        logger.setLevel(getattr(logging, log_level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def process_browser_data(self,
                           data: Union[str, Dict[str, Any]],
                           context: str,
                           data_category: DataCategory,
                           processing_purpose: str,
                           legal_basis: str,
                           user_id: Optional[str] = None,
                           encrypt_sensitive: bool = True,
                           scrub_pii: bool = True,
                           min_pii_confidence: float = 0.7) -> Dict[str, Any]:
        """
        Process browser data with comprehensive security and privacy protection.
        
        Args:
            data: Data to process (text or dict)
            context: Context of the data (url, form_data, screenshot, etc.)
            data_category: Category of data for retention policies
            processing_purpose: Purpose of processing
            legal_basis: Legal basis for processing
            user_id: Optional user identifier
            encrypt_sensitive: Whether to encrypt sensitive data
            scrub_pii: Whether to scrub PII from text data
            min_pii_confidence: Minimum confidence for PII scrubbing
            
        Returns:
            Dict[str, Any]: Processed data with security and privacy metadata
        """
        result = {
            "original_data": data,
            "processed_data": data,
            "security_metadata": {},
            "privacy_metadata": {},
            "processing_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Step 1: Input sanitization for security
            if isinstance(data, str):
                sanitized_data = self.security_manager.sanitize_input(data, context)
                result["processed_data"] = sanitized_data
                result["security_metadata"]["sanitized"] = sanitized_data != data
            elif isinstance(data, dict):
                sanitized_data = {}
                for key, value in data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = self.security_manager.sanitize_input(value, context)
                    else:
                        sanitized_data[key] = value
                result["processed_data"] = sanitized_data
                result["security_metadata"]["sanitized"] = sanitized_data != data
            
            # Step 2: PII detection and scrubbing
            pii_detections = []
            if scrub_pii:
                if isinstance(result["processed_data"], str):
                    scrubbed_text, detections = self.privacy_manager.scrub_pii(
                        result["processed_data"], 
                        context, 
                        min_pii_confidence
                    )
                    result["processed_data"] = scrubbed_text
                    pii_detections = detections
                elif isinstance(result["processed_data"], dict):
                    # Process each string field in the dict
                    scrubbed_dict = {}
                    for key, value in result["processed_data"].items():
                        if isinstance(value, str):
                            scrubbed_value, field_detections = self.privacy_manager.scrub_pii(
                                value, f"{context}_{key}", min_pii_confidence
                            )
                            scrubbed_dict[key] = scrubbed_value
                            pii_detections.extend(field_detections)
                        else:
                            scrubbed_dict[key] = value
                    result["processed_data"] = scrubbed_dict
            
            # Step 3: Data minimization
            if isinstance(result["processed_data"], dict):
                minimized_data = self.privacy_manager.minimize_data(
                    result["processed_data"], 
                    processing_purpose
                )
                result["processed_data"] = minimized_data
                result["privacy_metadata"]["minimized"] = minimized_data != result["processed_data"]
            
            # Step 4: Encryption of sensitive data
            encrypted = False
            if encrypt_sensitive and self._is_sensitive_data(data_category, pii_detections):
                encrypted_data = self.security_manager.encrypt_sensitive_data(
                    result["processed_data"], 
                    f"{data_category.value}_{context}"
                )
                result["processed_data"] = encrypted_data
                result["security_metadata"]["encrypted"] = True
                encrypted = True
            
            # Step 5: Record processing activity
            pii_types = [d.pii_type for d in pii_detections]
            record_id = self.privacy_manager.record_data_processing(
                data_category=data_category,
                processing_purpose=processing_purpose,
                legal_basis=legal_basis,
                data_source=f"browser_{context}",
                data_subject_id=user_id,
                pii_detected=pii_types,
                anonymized=False,  # We scrubbed but didn't anonymize
                encrypted=encrypted
            )
            
            # Step 6: Update metadata
            result["privacy_metadata"].update({
                "pii_detected": len(pii_detections),
                "pii_types": [pii.value for pii in pii_types],
                "data_category": data_category.value,
                "processing_record_id": record_id
            })
            
            result["security_metadata"].update({
                "user_id": user_id,
                "context": context,
                "legal_basis": legal_basis
            })
            
            self.logger.info(
                f"Processed {context} data: PII={len(pii_detections)}, "
                f"Encrypted={encrypted}, Category={data_category.value}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing browser data: {e}")
            
            # Log security event for processing failure
            self.security_manager._log_security_event(
                SecurityEventType.SECURITY_VIOLATION,
                "data_processing_error",
                {
                    "context": context,
                    "error": str(e),
                    "data_category": data_category.value
                },
                severity="ERROR",
                user_id=user_id
            )
            
            raise
    
    def _is_sensitive_data(self, 
                          data_category: DataCategory, 
                          pii_detections: List[PIIDetection]) -> bool:
        """Determine if data should be encrypted based on category and PII content."""
        sensitive_categories = {
            DataCategory.SENSITIVE_DATA,
            DataCategory.FINANCIAL_DATA,
            DataCategory.HEALTH_DATA,
            DataCategory.BIOMETRIC_DATA
        }
        
        sensitive_pii_types = {
            PIIType.SSN,
            PIIType.CREDIT_CARD,
            PIIType.PASSPORT,
            PIIType.DRIVER_LICENSE,
            PIIType.BANK_ACCOUNT,
            PIIType.MEDICAL_ID
        }
        
        # Encrypt if data category is sensitive
        if data_category in sensitive_categories:
            return True
        
        # Encrypt if sensitive PII is detected
        detected_pii_types = {d.pii_type for d in pii_detections}
        if detected_pii_types.intersection(sensitive_pii_types):
            return True
        
        return False
    
    def create_secure_browser_session(self, 
                                    user_id: str,
                                    browser_config: Dict[str, Any],
                                    session_purpose: str) -> str:
        """
        Create a secure browser session with comprehensive logging.
        
        Args:
            user_id: User identifier
            browser_config: Browser configuration
            session_purpose: Purpose of the browser session
            
        Returns:
            str: Secure session token
        """
        # Sanitize browser configuration
        sanitized_config = {}
        for key, value in browser_config.items():
            if isinstance(value, str):
                sanitized_config[key] = self.security_manager.sanitize_input(
                    value, f"browser_config_{key}"
                )
            else:
                sanitized_config[key] = value
        
        # Create session data
        session_data = {
            "browser_config": sanitized_config,
            "purpose": session_purpose,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Create secure session token
        session_token = self.security_manager.create_secure_session_token(
            user_id, session_data
        )
        
        # Record session creation for privacy compliance
        self.privacy_manager.record_data_processing(
            data_category=DataCategory.TECHNICAL_DATA,
            processing_purpose=f"browser_session_{session_purpose}",
            legal_basis="legitimate_interest",
            data_source="browser_session_manager",
            data_subject_id=user_id,
            pii_detected=[],
            anonymized=False,
            encrypted=True  # Session tokens are encrypted
        )
        
        self.logger.info(f"Created secure browser session for user: {user_id}")
        
        return session_token
    
    def validate_and_process_browser_input(self,
                                         user_input: str,
                                         input_type: str,
                                         user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate and process browser input with security and privacy checks.
        
        Args:
            user_input: Raw user input
            input_type: Type of input (url, selector, text, etc.)
            user_id: Optional user identifier
            
        Returns:
            Dict[str, Any]: Validation and processing results
        """
        result = {
            "original_input": user_input,
            "processed_input": user_input,
            "valid": True,
            "security_issues": [],
            "privacy_issues": [],
            "recommendations": []
        }
        
        try:
            # Security validation and sanitization
            sanitized_input = self.security_manager.sanitize_input(user_input, input_type)
            
            if sanitized_input != user_input:
                result["security_issues"].append("Input contained potentially malicious content")
                result["recommendations"].append("Input was sanitized for security")
            
            result["processed_input"] = sanitized_input
            
            # Privacy validation - check for PII
            pii_detections = self.privacy_manager.detect_pii(sanitized_input, input_type)
            
            if pii_detections:
                high_confidence_pii = [d for d in pii_detections if d.confidence >= 0.8]
                if high_confidence_pii:
                    result["privacy_issues"].append(
                        f"Input contains {len(high_confidence_pii)} high-confidence PII instances"
                    )
                    result["recommendations"].append("Consider removing or masking PII before processing")
                
                # Record PII detection
                pii_types = [d.pii_type for d in pii_detections]
                self.privacy_manager.record_data_processing(
                    data_category=DataCategory.PERSONAL_DATA,
                    processing_purpose=f"input_validation_{input_type}",
                    legal_basis="legitimate_interest",
                    data_source="user_input",
                    data_subject_id=user_id,
                    pii_detected=pii_types,
                    anonymized=False,
                    encrypted=False
                )
            
            # Determine if input is valid for processing
            if len(result["security_issues"]) > 0:
                result["valid"] = False
                result["recommendations"].append("Address security issues before proceeding")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error validating browser input: {e}")
            result["valid"] = False
            result["security_issues"].append(f"Validation error: {str(e)}")
            return result
    
    def generate_comprehensive_report(self,
                                    start_date: datetime,
                                    end_date: datetime) -> Dict[str, Any]:
        """
        Generate comprehensive security and privacy report.
        
        Args:
            start_date: Start of reporting period
            end_date: End of reporting period
            
        Returns:
            Dict[str, Any]: Comprehensive report
        """
        # Generate security report
        security_report = self.security_manager.generate_security_report()
        
        # Generate privacy/compliance report
        privacy_report = self.privacy_manager.generate_compliance_report(
            start_date, end_date
        )
        
        # Combine reports
        comprehensive_report = {
            "report_type": "comprehensive_security_privacy",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "security": {
                "total_security_events": security_report["total_events"],
                "event_type_counts": security_report["event_type_counts"],
                "severity_counts": security_report["severity_counts"],
                "active_sessions": security_report["active_sessions"]
            },
            "privacy": {
                "total_processing_records": privacy_report.total_records_processed,
                "pii_detections": privacy_report.pii_detections,
                "data_categories": privacy_report.data_categories,
                "compliance_violations": privacy_report.compliance_violations,
                "recommendations": privacy_report.recommendations
            },
            "summary": {
                "security_status": self._assess_security_status(security_report),
                "privacy_compliance": self._assess_privacy_compliance(privacy_report),
                "overall_risk_level": "low"  # Would be calculated based on findings
            }
        }
        
        # Add cross-cutting analysis
        comprehensive_report["cross_analysis"] = self._perform_cross_analysis(
            security_report, privacy_report
        )
        
        return comprehensive_report
    
    def _assess_security_status(self, security_report: Dict[str, Any]) -> str:
        """Assess overall security status."""
        severity_counts = security_report.get("severity_counts", {})
        
        if severity_counts.get("CRITICAL", 0) > 0:
            return "critical"
        elif severity_counts.get("ERROR", 0) > 5:
            return "poor"
        elif severity_counts.get("WARNING", 0) > 10:
            return "fair"
        else:
            return "good"
    
    def _assess_privacy_compliance(self, privacy_report) -> str:
        """Assess privacy compliance status."""
        violations = privacy_report.compliance_violations
        
        high_severity_violations = [
            v for v in violations if v.get("severity") == "high"
        ]
        
        if len(high_severity_violations) > 0:
            return "non_compliant"
        elif len(violations) > 5:
            return "needs_attention"
        else:
            return "compliant"
    
    def _perform_cross_analysis(self, 
                               security_report: Dict[str, Any], 
                               privacy_report) -> Dict[str, Any]:
        """Perform cross-analysis of security and privacy data."""
        analysis = {
            "data_protection_effectiveness": "good",
            "risk_areas": [],
            "recommendations": []
        }
        
        # Check for patterns indicating systemic issues
        security_violations = security_report.get("event_type_counts", {}).get("security_violation", 0)
        privacy_violations = len(privacy_report.compliance_violations)
        
        if security_violations > 0 and privacy_violations > 0:
            analysis["risk_areas"].append("Multiple security and privacy violations detected")
            analysis["recommendations"].append("Review data handling processes comprehensively")
            analysis["data_protection_effectiveness"] = "needs_improvement"
        
        return analysis
    
    def cleanup_expired_data(self, max_age_hours: int = 24):
        """
        Clean up expired sessions and apply retention policies.
        
        Args:
            max_age_hours: Maximum age for session cleanup
        """
        # Clean up expired sessions
        self.security_manager.cleanup_expired_sessions(max_age_hours)
        
        # Apply retention policies to processing records
        current_time = datetime.now(timezone.utc)
        records_to_remove = []
        
        for i, record in enumerate(self.privacy_manager.processing_records):
            processed_data, action = self.privacy_manager.apply_retention_policy(
                record.data_category,
                {"record": record},  # Wrap record for processing
                record.timestamp
            )
            
            if processed_data is None:  # Record should be deleted
                records_to_remove.append(i)
        
        # Remove records marked for deletion (in reverse order to maintain indices)
        for i in reversed(records_to_remove):
            del self.privacy_manager.processing_records[i]
        
        if records_to_remove:
            self.logger.info(f"Cleaned up {len(records_to_remove)} expired processing records")
    
    def get_user_data_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary of all data associated with a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict[str, Any]: User data summary
        """
        # Get processing records for user
        user_records = self.privacy_manager.get_data_subject_records(user_id)
        
        # Get security events for user
        user_security_events = self.security_manager.get_audit_events(user_id=user_id)
        
        # Analyze data
        data_categories = set(record.data_category for record in user_records)
        pii_types = set()
        for record in user_records:
            pii_types.update(record.pii_detected)
        
        summary = {
            "user_id": user_id,
            "total_processing_records": len(user_records),
            "total_security_events": len(user_security_events),
            "data_categories": [cat.value for cat in data_categories],
            "pii_types_detected": [pii.value for pii in pii_types],
            "earliest_record": min(record.timestamp for record in user_records) if user_records else None,
            "latest_record": max(record.timestamp for record in user_records) if user_records else None,
            "data_retention_status": self._check_user_data_retention(user_records)
        }
        
        return summary
    
    def _check_user_data_retention(self, user_records: List) -> Dict[str, Any]:
        """Check retention status for user data."""
        current_time = datetime.now(timezone.utc)
        retention_status = {
            "compliant": 0,
            "approaching_limit": 0,
            "exceeded_limit": 0
        }
        
        for record in user_records:
            policy = self.privacy_manager.retention_policies.get(record.data_category)
            if policy:
                age_days = (current_time - record.timestamp).days
                limit_days = policy.retention_period_days
                
                if age_days > limit_days:
                    retention_status["exceeded_limit"] += 1
                elif age_days > limit_days * 0.9:  # Within 10% of limit
                    retention_status["approaching_limit"] += 1
                else:
                    retention_status["compliant"] += 1
        
        return retention_status