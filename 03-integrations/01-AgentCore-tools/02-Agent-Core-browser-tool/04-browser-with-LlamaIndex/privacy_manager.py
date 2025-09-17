"""
Privacy Manager for LlamaIndex-AgentCore Browser Integration

This module provides comprehensive privacy and data protection including:
- PII detection and scrubbing
- Data minimization and retention policies
- Compliance reporting and audit trail functionality
- Secure data handling and storage practices

Requirements: 5.2, 5.4
"""

import re
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError


class PIIType(Enum):
    """Types of Personally Identifiable Information."""
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    EMAIL = "email"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    MEDICAL_ID = "medical_id"
    CUSTOM = "custom"


class DataCategory(Enum):
    """Categories of data for retention policies."""
    PERSONAL_DATA = "personal_data"
    SENSITIVE_DATA = "sensitive_data"
    FINANCIAL_DATA = "financial_data"
    HEALTH_DATA = "health_data"
    BIOMETRIC_DATA = "biometric_data"
    BEHAVIORAL_DATA = "behavioral_data"
    TECHNICAL_DATA = "technical_data"
    OPERATIONAL_DATA = "operational_data"


class RetentionAction(Enum):
    """Actions to take when retention period expires."""
    DELETE = "delete"
    ANONYMIZE = "anonymize"
    ARCHIVE = "archive"
    REVIEW = "review"


@dataclass
class PIIDetection:
    """Result of PII detection."""
    pii_type: PIIType
    value: str
    confidence: float
    start_position: int
    end_position: int
    context: str
    replacement: str


@dataclass
class DataRetentionPolicy:
    """Data retention policy configuration."""
    data_category: DataCategory
    retention_period_days: int
    retention_action: RetentionAction
    description: str
    legal_basis: Optional[str] = None
    exceptions: List[str] = None


@dataclass
class DataProcessingRecord:
    """Record of data processing activity."""
    record_id: str
    timestamp: datetime
    data_category: DataCategory
    processing_purpose: str
    data_subject_id: Optional[str]
    legal_basis: str
    data_source: str
    data_destination: Optional[str]
    retention_policy: str
    pii_detected: List[PIIType]
    anonymized: bool
    encrypted: bool


@dataclass
class ComplianceReport:
    """Compliance report data."""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    total_records_processed: int
    pii_detections: Dict[str, int]
    data_categories: Dict[str, int]
    retention_actions: Dict[str, int]
    compliance_violations: List[Dict[str, Any]]
    recommendations: List[str]


class PrivacyManager:
    """
    Manages privacy and data protection for the LlamaIndex-AgentCore integration.
    
    Provides:
    - PII detection and scrubbing using advanced pattern matching
    - Data minimization and retention policy enforcement
    - Compliance reporting and audit trail functionality
    - Secure data handling and storage practices
    """
    
    # PII detection patterns with confidence scores
    PII_PATTERNS = {
        PIIType.SSN: [
            (r'\b\d{3}-\d{2}-\d{4}\b', 0.95),  # XXX-XX-XXXX
            (r'\b\d{3}\s\d{2}\s\d{4}\b', 0.90),  # XXX XX XXXX
            (r'\b\d{9}\b', 0.70),  # XXXXXXXXX (lower confidence)
        ],
        PIIType.CREDIT_CARD: [
            (r'\b4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 0.95),  # Visa
            (r'\b5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 0.95),  # MasterCard
            (r'\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b', 0.95),  # American Express
            (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', 0.80),  # Generic
        ],
        PIIType.EMAIL: [
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 0.95),
        ],
        PIIType.PHONE: [
            (r'\b\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b', 0.90),  # US
            (r'\b\+?[1-9]\d{1,14}\b', 0.70),  # International (lower confidence)
        ],
        PIIType.IP_ADDRESS: [
            (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', 0.85),  # IPv4
            (r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b', 0.90),  # IPv6
        ],
        PIIType.DATE_OF_BIRTH: [
            (r'\b(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/(19|20)\d{2}\b', 0.85),  # MM/DD/YYYY
            (r'\b(19|20)\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b', 0.85),  # YYYY-MM-DD
        ],
        PIIType.BANK_ACCOUNT: [
            (r'\b\d{8,17}\b', 0.60),  # Generic bank account (low confidence)
        ],
    }
    
    # Common name patterns (basic detection)
    NAME_PATTERNS = [
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',  # First Last
        r'\b[A-Z][a-z]+, [A-Z][a-z]+\b',  # Last, First
    ]
    
    # Default retention policies
    DEFAULT_RETENTION_POLICIES = {
        DataCategory.PERSONAL_DATA: DataRetentionPolicy(
            data_category=DataCategory.PERSONAL_DATA,
            retention_period_days=365,
            retention_action=RetentionAction.ANONYMIZE,
            description="Personal data retained for 1 year then anonymized",
            legal_basis="Legitimate interest"
        ),
        DataCategory.SENSITIVE_DATA: DataRetentionPolicy(
            data_category=DataCategory.SENSITIVE_DATA,
            retention_period_days=90,
            retention_action=RetentionAction.DELETE,
            description="Sensitive data deleted after 90 days",
            legal_basis="Consent"
        ),
        DataCategory.FINANCIAL_DATA: DataRetentionPolicy(
            data_category=DataCategory.FINANCIAL_DATA,
            retention_period_days=2555,  # 7 years
            retention_action=RetentionAction.ARCHIVE,
            description="Financial data archived after 7 years for compliance",
            legal_basis="Legal obligation"
        ),
        DataCategory.TECHNICAL_DATA: DataRetentionPolicy(
            data_category=DataCategory.TECHNICAL_DATA,
            retention_period_days=180,
            retention_action=RetentionAction.ANONYMIZE,
            description="Technical data anonymized after 6 months",
            legal_basis="Legitimate interest"
        ),
    }
    
    def __init__(self, 
                 aws_region: str = "us-east-1",
                 log_level: str = "INFO",
                 custom_pii_patterns: Optional[Dict[PIIType, List[Tuple[str, float]]]] = None,
                 retention_policies: Optional[Dict[DataCategory, DataRetentionPolicy]] = None):
        """
        Initialize PrivacyManager.
        
        Args:
            aws_region: AWS region for services
            log_level: Logging level
            custom_pii_patterns: Custom PII detection patterns
            retention_policies: Custom retention policies
        """
        self.aws_region = aws_region
        self.logger = self._setup_logging(log_level)
        
        # Merge custom PII patterns with defaults
        self.pii_patterns = self.PII_PATTERNS.copy()
        if custom_pii_patterns:
            for pii_type, patterns in custom_pii_patterns.items():
                if pii_type in self.pii_patterns:
                    self.pii_patterns[pii_type].extend(patterns)
                else:
                    self.pii_patterns[pii_type] = patterns
        
        # Set up retention policies
        self.retention_policies = retention_policies or self.DEFAULT_RETENTION_POLICIES.copy()
        
        # Data processing records
        self.processing_records: List[DataProcessingRecord] = []
        
        # Initialize AWS clients
        self.s3_client = None
        self.logs_client = None
        self._initialize_aws_clients()
        
        self.logger.info("PrivacyManager initialized successfully")
    
    def _setup_logging(self, log_level: str) -> logging.Logger:
        """Set up privacy logging."""
        logger = logging.getLogger("llamaindex_agentcore_privacy")
        logger.setLevel(getattr(logging, log_level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _initialize_aws_clients(self):
        """Initialize AWS clients for privacy operations."""
        try:
            self.s3_client = boto3.client('s3', region_name=self.aws_region)
            self.logs_client = boto3.client('logs', region_name=self.aws_region)
            self.logger.info("AWS clients initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AWS clients: {e}")
            self.s3_client = None
            self.logs_client = None
    
    def detect_pii(self, text: str, context: str = "general") -> List[PIIDetection]:
        """
        Detect PII in text using pattern matching.
        
        Args:
            text: Text to analyze for PII
            context: Context of the text for better detection
            
        Returns:
            List[PIIDetection]: List of detected PII instances
        """
        detections = []
        
        for pii_type, patterns in self.pii_patterns.items():
            for pattern, confidence in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    # Extract context around the match
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    match_context = text[start:end]
                    
                    # Generate replacement based on PII type
                    replacement = self._generate_replacement(pii_type, match.group())
                    
                    detection = PIIDetection(
                        pii_type=pii_type,
                        value=match.group(),
                        confidence=confidence,
                        start_position=match.start(),
                        end_position=match.end(),
                        context=match_context,
                        replacement=replacement
                    )
                    
                    detections.append(detection)
        
        # Detect names using basic patterns
        name_detections = self._detect_names(text)
        detections.extend(name_detections)
        
        # Sort by position and remove overlaps
        detections = self._remove_overlapping_detections(detections)
        
        self.logger.info(f"Detected {len(detections)} PII instances in {context}")
        
        return detections
    
    def _detect_names(self, text: str) -> List[PIIDetection]:
        """Detect potential names in text."""
        detections = []
        
        for pattern in self.NAME_PATTERNS:
            matches = re.finditer(pattern, text)
            
            for match in matches:
                # Basic validation - avoid common false positives
                name = match.group()
                if self._is_likely_name(name):
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    match_context = text[start:end]
                    
                    detection = PIIDetection(
                        pii_type=PIIType.NAME,
                        value=name,
                        confidence=0.70,  # Lower confidence for name detection
                        start_position=match.start(),
                        end_position=match.end(),
                        context=match_context,
                        replacement=self._generate_replacement(PIIType.NAME, name)
                    )
                    
                    detections.append(detection)
        
        return detections
    
    def _is_likely_name(self, text: str) -> bool:
        """Basic validation to check if text is likely a name."""
        # Avoid common false positives
        false_positives = {
            'New York', 'Los Angeles', 'San Francisco', 'Las Vegas',
            'United States', 'North America', 'South America',
            'First Name', 'Last Name', 'Full Name', 'User Name',
            'Test User', 'John Doe', 'Jane Doe'
        }
        
        return text not in false_positives and len(text.split()) <= 3
    
    def _generate_replacement(self, pii_type: PIIType, original_value: str) -> str:
        """Generate appropriate replacement for detected PII."""
        replacements = {
            PIIType.SSN: "[SSN-REDACTED]",
            PIIType.CREDIT_CARD: "[CARD-REDACTED]",
            PIIType.EMAIL: "[EMAIL-REDACTED]",
            PIIType.PHONE: "[PHONE-REDACTED]",
            PIIType.IP_ADDRESS: "[IP-REDACTED]",
            PIIType.NAME: "[NAME-REDACTED]",
            PIIType.ADDRESS: "[ADDRESS-REDACTED]",
            PIIType.DATE_OF_BIRTH: "[DOB-REDACTED]",
            PIIType.PASSPORT: "[PASSPORT-REDACTED]",
            PIIType.DRIVER_LICENSE: "[LICENSE-REDACTED]",
            PIIType.BANK_ACCOUNT: "[ACCOUNT-REDACTED]",
            PIIType.MEDICAL_ID: "[MEDICAL-ID-REDACTED]",
        }
        
        return replacements.get(pii_type, "[PII-REDACTED]")
    
    def _remove_overlapping_detections(self, detections: List[PIIDetection]) -> List[PIIDetection]:
        """Remove overlapping PII detections, keeping highest confidence."""
        if not detections:
            return detections
        
        # Sort by position
        sorted_detections = sorted(detections, key=lambda x: x.start_position)
        
        filtered = []
        for detection in sorted_detections:
            # Check for overlap with existing detections
            overlaps = False
            for existing in filtered:
                if (detection.start_position < existing.end_position and 
                    detection.end_position > existing.start_position):
                    # Overlap detected - keep higher confidence
                    if detection.confidence > existing.confidence:
                        filtered.remove(existing)
                        filtered.append(detection)
                    overlaps = True
                    break
            
            if not overlaps:
                filtered.append(detection)
        
        return filtered
    
    def scrub_pii(self, text: str, 
                  context: str = "general",
                  min_confidence: float = 0.7) -> Tuple[str, List[PIIDetection]]:
        """
        Remove or mask PII from text content.
        
        Args:
            text: Text to scrub
            context: Context for better detection
            min_confidence: Minimum confidence threshold for scrubbing
            
        Returns:
            Tuple[str, List[PIIDetection]]: Scrubbed text and list of detections
        """
        detections = self.detect_pii(text, context)
        
        # Filter by confidence threshold
        high_confidence_detections = [
            d for d in detections if d.confidence >= min_confidence
        ]
        
        # Apply replacements in reverse order to maintain positions
        scrubbed_text = text
        for detection in reversed(high_confidence_detections):
            scrubbed_text = (
                scrubbed_text[:detection.start_position] +
                detection.replacement +
                scrubbed_text[detection.end_position:]
            )
        
        self.logger.info(
            f"Scrubbed {len(high_confidence_detections)} PII instances from {context}"
        )
        
        return scrubbed_text, high_confidence_detections
    
    def anonymize_data(self, data: Dict[str, Any], 
                      anonymization_rules: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Anonymize structured data by removing or hashing identifiers.
        
        Args:
            data: Data to anonymize
            anonymization_rules: Custom anonymization rules
            
        Returns:
            Dict[str, Any]: Anonymized data
        """
        default_rules = {
            'user_id': 'hash',
            'session_id': 'hash',
            'ip_address': 'remove',
            'email': 'remove',
            'name': 'remove',
            'phone': 'remove',
            'address': 'remove',
        }
        
        rules = anonymization_rules or default_rules
        anonymized = data.copy()
        
        for field, action in rules.items():
            if field in anonymized:
                if action == 'remove':
                    del anonymized[field]
                elif action == 'hash':
                    original_value = str(anonymized[field])
                    hashed_value = hashlib.sha256(original_value.encode()).hexdigest()[:16]
                    anonymized[field] = f"anon_{hashed_value}"
                elif action == 'mask':
                    original_value = str(anonymized[field])
                    if len(original_value) > 4:
                        anonymized[field] = original_value[:2] + '*' * (len(original_value) - 4) + original_value[-2:]
                    else:
                        anonymized[field] = '*' * len(original_value)
        
        return anonymized
    
    def record_data_processing(self, 
                             data_category: DataCategory,
                             processing_purpose: str,
                             legal_basis: str,
                             data_source: str,
                             data_subject_id: Optional[str] = None,
                             data_destination: Optional[str] = None,
                             pii_detected: Optional[List[PIIType]] = None,
                             anonymized: bool = False,
                             encrypted: bool = False) -> str:
        """
        Record data processing activity for compliance.
        
        Args:
            data_category: Category of data being processed
            processing_purpose: Purpose of processing
            legal_basis: Legal basis for processing
            data_source: Source of the data
            data_subject_id: Optional identifier for data subject
            data_destination: Optional destination for data
            pii_detected: List of PII types detected
            anonymized: Whether data was anonymized
            encrypted: Whether data was encrypted
            
        Returns:
            str: Record ID
        """
        record_id = hashlib.sha256(
            f"{datetime.now().isoformat()}{data_source}{processing_purpose}".encode()
        ).hexdigest()[:16]
        
        # Get retention policy for this data category
        retention_policy = self.retention_policies.get(data_category)
        policy_name = retention_policy.description if retention_policy else "default"
        
        record = DataProcessingRecord(
            record_id=record_id,
            timestamp=datetime.now(timezone.utc),
            data_category=data_category,
            processing_purpose=processing_purpose,
            data_subject_id=data_subject_id,
            legal_basis=legal_basis,
            data_source=data_source,
            data_destination=data_destination,
            retention_policy=policy_name,
            pii_detected=pii_detected or [],
            anonymized=anonymized,
            encrypted=encrypted
        )
        
        self.processing_records.append(record)
        
        self.logger.info(f"Recorded data processing activity: {record_id}")
        
        return record_id
    
    def apply_retention_policy(self, 
                             data_category: DataCategory,
                             data: Dict[str, Any],
                             created_at: datetime) -> Tuple[Optional[Dict[str, Any]], RetentionAction]:
        """
        Apply retention policy to data based on age and category.
        
        Args:
            data_category: Category of data
            data: Data to evaluate
            created_at: When data was created
            
        Returns:
            Tuple[Optional[Dict], RetentionAction]: Processed data and action taken
        """
        policy = self.retention_policies.get(data_category)
        if not policy:
            self.logger.warning(f"No retention policy found for {data_category}")
            return data, RetentionAction.REVIEW
        
        # Check if data has exceeded retention period
        age_days = (datetime.now(timezone.utc) - created_at).days
        
        if age_days <= policy.retention_period_days:
            return data, RetentionAction.REVIEW  # No action needed yet
        
        # Apply retention action
        if policy.retention_action == RetentionAction.DELETE:
            self.logger.info(f"Deleting data due to retention policy: {data_category}")
            return None, RetentionAction.DELETE
        
        elif policy.retention_action == RetentionAction.ANONYMIZE:
            self.logger.info(f"Anonymizing data due to retention policy: {data_category}")
            anonymized_data = self.anonymize_data(data)
            return anonymized_data, RetentionAction.ANONYMIZE
        
        elif policy.retention_action == RetentionAction.ARCHIVE:
            self.logger.info(f"Archiving data due to retention policy: {data_category}")
            # In a real implementation, this would move data to long-term storage
            return data, RetentionAction.ARCHIVE
        
        else:
            return data, RetentionAction.REVIEW
    
    def minimize_data(self, data: Dict[str, Any], 
                     purpose: str,
                     required_fields: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        Apply data minimization principles by keeping only necessary fields.
        
        Args:
            data: Original data
            purpose: Purpose for which data is needed
            required_fields: Set of required field names
            
        Returns:
            Dict[str, Any]: Minimized data
        """
        # Define purpose-based field requirements
        purpose_requirements = {
            'authentication': {'user_id', 'session_id', 'timestamp'},
            'analytics': {'user_id', 'action', 'timestamp', 'page_url'},
            'logging': {'timestamp', 'level', 'message', 'source'},
            'browser_automation': {'url', 'action', 'selector', 'timestamp'},
            'captcha_solving': {'image_data', 'captcha_type', 'timestamp'},
        }
        
        # Get required fields for purpose
        if required_fields:
            fields_to_keep = required_fields
        else:
            fields_to_keep = purpose_requirements.get(purpose, set(data.keys()))
        
        # Keep only required fields
        minimized_data = {
            key: value for key, value in data.items() 
            if key in fields_to_keep
        }
        
        removed_fields = set(data.keys()) - set(minimized_data.keys())
        if removed_fields:
            self.logger.info(f"Minimized data for {purpose}: removed {len(removed_fields)} fields")
        
        return minimized_data
    
    def generate_compliance_report(self, 
                                 start_date: datetime,
                                 end_date: datetime) -> ComplianceReport:
        """
        Generate compliance report for specified period.
        
        Args:
            start_date: Start of reporting period
            end_date: End of reporting period
            
        Returns:
            ComplianceReport: Comprehensive compliance report
        """
        report_id = hashlib.sha256(
            f"compliance_report_{start_date.isoformat()}_{end_date.isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Filter records for the period
        period_records = [
            record for record in self.processing_records
            if start_date <= record.timestamp <= end_date
        ]
        
        # Analyze PII detections
        pii_counts = {}
        for record in period_records:
            for pii_type in record.pii_detected:
                pii_counts[pii_type.value] = pii_counts.get(pii_type.value, 0) + 1
        
        # Analyze data categories
        category_counts = {}
        for record in period_records:
            category = record.data_category.value
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Check for compliance violations
        violations = self._check_compliance_violations(period_records)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(period_records, violations)
        
        report = ComplianceReport(
            report_id=report_id,
            generated_at=datetime.now(timezone.utc),
            period_start=start_date,
            period_end=end_date,
            total_records_processed=len(period_records),
            pii_detections=pii_counts,
            data_categories=category_counts,
            retention_actions={},  # Would be populated in real implementation
            compliance_violations=violations,
            recommendations=recommendations
        )
        
        self.logger.info(f"Generated compliance report: {report_id}")
        
        return report
    
    def _check_compliance_violations(self, records: List[DataProcessingRecord]) -> List[Dict[str, Any]]:
        """Check for potential compliance violations."""
        violations = []
        
        # Check for missing legal basis
        for record in records:
            if not record.legal_basis or record.legal_basis.lower() in ['none', 'unknown']:
                violations.append({
                    'type': 'missing_legal_basis',
                    'record_id': record.record_id,
                    'description': 'Processing record lacks valid legal basis',
                    'severity': 'high'
                })
        
        # Check for unencrypted sensitive data
        sensitive_categories = {DataCategory.SENSITIVE_DATA, DataCategory.FINANCIAL_DATA, 
                              DataCategory.HEALTH_DATA, DataCategory.BIOMETRIC_DATA}
        
        for record in records:
            if record.data_category in sensitive_categories and not record.encrypted:
                violations.append({
                    'type': 'unencrypted_sensitive_data',
                    'record_id': record.record_id,
                    'description': f'Sensitive data ({record.data_category.value}) not encrypted',
                    'severity': 'high'
                })
        
        # Check for excessive data retention
        for record in records:
            policy = self.retention_policies.get(record.data_category)
            if policy:
                age_days = (datetime.now(timezone.utc) - record.timestamp).days
                if age_days > policy.retention_period_days * 1.1:  # 10% grace period
                    violations.append({
                        'type': 'excessive_retention',
                        'record_id': record.record_id,
                        'description': f'Data retained beyond policy limit ({age_days} > {policy.retention_period_days} days)',
                        'severity': 'medium'
                    })
        
        return violations
    
    def _generate_recommendations(self, 
                                records: List[DataProcessingRecord],
                                violations: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # High-level recommendations based on violations
        violation_types = {v['type'] for v in violations}
        
        if 'missing_legal_basis' in violation_types:
            recommendations.append(
                "Ensure all data processing activities have a valid legal basis documented"
            )
        
        if 'unencrypted_sensitive_data' in violation_types:
            recommendations.append(
                "Implement encryption for all sensitive data categories"
            )
        
        if 'excessive_retention' in violation_types:
            recommendations.append(
                "Review and enforce data retention policies more strictly"
            )
        
        # Analyze PII detection patterns
        total_pii_detections = sum(len(record.pii_detected) for record in records)
        if total_pii_detections > len(records) * 0.5:  # More than 50% of records have PII
            recommendations.append(
                "Consider implementing stronger PII detection and anonymization processes"
            )
        
        # Check anonymization rates
        anonymized_count = sum(1 for record in records if record.anonymized)
        if anonymized_count < len(records) * 0.3:  # Less than 30% anonymized
            recommendations.append(
                "Increase use of data anonymization techniques to reduce privacy risks"
            )
        
        return recommendations
    
    def export_processing_records(self, 
                                output_format: str = "json",
                                include_pii: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Export processing records for audit or compliance purposes.
        
        Args:
            output_format: Format for export (json, csv)
            include_pii: Whether to include PII details (should be false for most exports)
            
        Returns:
            Union[str, Dict]: Exported data
        """
        records_data = []
        
        for record in self.processing_records:
            record_dict = asdict(record)
            
            # Remove PII details if not requested
            if not include_pii:
                record_dict['pii_detected'] = [pii.value for pii in record.pii_detected]
                if record.data_subject_id:
                    record_dict['data_subject_id'] = hashlib.sha256(
                        record.data_subject_id.encode()
                    ).hexdigest()[:16]
            
            records_data.append(record_dict)
        
        if output_format.lower() == "json":
            return json.dumps(records_data, indent=2, default=str)
        else:
            return {"records": records_data}
    
    def get_data_subject_records(self, data_subject_id: str) -> List[DataProcessingRecord]:
        """
        Get all processing records for a specific data subject.
        
        Args:
            data_subject_id: Identifier for the data subject
            
        Returns:
            List[DataProcessingRecord]: Records for the data subject
        """
        return [
            record for record in self.processing_records
            if record.data_subject_id == data_subject_id
        ]
    
    def delete_data_subject_records(self, data_subject_id: str) -> int:
        """
        Delete all records for a data subject (right to erasure).
        
        Args:
            data_subject_id: Identifier for the data subject
            
        Returns:
            int: Number of records deleted
        """
        initial_count = len(self.processing_records)
        
        self.processing_records = [
            record for record in self.processing_records
            if record.data_subject_id != data_subject_id
        ]
        
        deleted_count = initial_count - len(self.processing_records)
        
        self.logger.info(f"Deleted {deleted_count} records for data subject: {data_subject_id}")
        
        return deleted_count