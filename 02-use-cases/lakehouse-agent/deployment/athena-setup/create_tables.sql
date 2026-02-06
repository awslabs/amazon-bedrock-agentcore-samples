-- Health Lakehouse Data Processing System - Athena Table Schema
-- This script creates the database and tables for storing health lakehouse data

-- Create database
CREATE DATABASE IF NOT EXISTS lakehouse_db;

-- Use the database
-- Note: In Athena, you must explicitly use the database in your queries

-- Create claims table with row-level access control support
CREATE EXTERNAL TABLE IF NOT EXISTS lakehouse_db.claims (
    claim_id STRING COMMENT 'Unique claim identifier',
    user_id STRING COMMENT 'User/patient email for row-level access control',
    patient_name STRING COMMENT 'Patient full name',
    patient_dob DATE COMMENT 'Patient date of birth',
    claim_date DATE COMMENT 'Date when claim occurred',
    claim_amount DECIMAL(10,2) COMMENT 'Total claim amount in USD',
    claim_type STRING COMMENT 'Type of claim: medical, prescription, hospital, emergency',
    claim_status STRING COMMENT 'Current status: pending, approved, denied, in_review, requires_info',
    provider_name STRING COMMENT 'Healthcare provider name',
    provider_npi STRING COMMENT 'National Provider Identifier',
    diagnosis_code STRING COMMENT 'ICD-10 diagnosis code',
    procedure_code STRING COMMENT 'CPT procedure code',
    submitted_date TIMESTAMP COMMENT 'When claim was submitted',
    processed_date TIMESTAMP COMMENT 'When claim was processed',
    approved_amount DECIMAL(10,2) COMMENT 'Approved claim amount',
    denial_reason STRING COMMENT 'Reason for denial if applicable',
    notes STRING COMMENT 'Additional notes or comments',
    created_by STRING COMMENT 'User who created the claim',
    last_modified_by STRING COMMENT 'User who last modified the claim',
    last_modified_date TIMESTAMP COMMENT 'Last modification timestamp'
)
COMMENT 'Health lakehouse data table with row-level access control'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET_NAME/lakehouse-data/claims/'
TBLPROPERTIES (
    'skip.header.line.count'='1',
    'classification'='csv'
);

-- Create users table for reference (optional, if you want to store user metadata)
CREATE EXTERNAL TABLE IF NOT EXISTS lakehouse_db.users (
    user_id STRING COMMENT 'User email address',
    user_name STRING COMMENT 'User full name',
    user_role STRING COMMENT 'User role: patient, adjuster, admin',
    department STRING COMMENT 'Department or region',
    created_date TIMESTAMP COMMENT 'User creation date'
)
COMMENT 'Users table for reference'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET_NAME/lakehouse-data/users/'
TBLPROPERTIES (
    'skip.header.line.count'='1',
    'classification'='csv'
);

-- Create audit log table for tracking access (optional)
CREATE EXTERNAL TABLE IF NOT EXISTS lakehouse_db.audit_log (
    log_id STRING COMMENT 'Unique log identifier',
    user_id STRING COMMENT 'User who performed the action',
    action STRING COMMENT 'Action performed: query, insert, update, delete',
    claim_id STRING COMMENT 'Claim ID affected',
    timestamp TIMESTAMP COMMENT 'When action was performed',
    ip_address STRING COMMENT 'User IP address',
    details STRING COMMENT 'Additional details about the action'
)
COMMENT 'Audit log for compliance and security'
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://YOUR_BUCKET_NAME/lakehouse-data/audit/'
TBLPROPERTIES (
    'skip.header.line.count'='1',
    'classification'='csv'
);
