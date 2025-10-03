#!/usr/bin/env python3
"""
DynamoDB Customer Data Population Script

This script populates the marketing-customer-data DynamoDB table with sample customer data
for testing and demonstration purposes.

Usage Examples:
    # Dry run to validate data generation
    python populate_dynamodb.py --dry-run --customers 100

    # Populate with 1000 customers and validate
    python populate_dynamodb.py --customers 1000 --validate

    # Populate specific table in different region
    python populate_dynamodb.py --table-name my-table --region us-west-2

    # Populate with custom settings and retry logic
    python populate_dynamodb.py --customers 5000 --max-purchases 10 --max-retries 5
"""

import boto3
import json
import random
import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid
from decimal import Decimal
from botocore.exceptions import ClientError, BotoCoreError


class DataValidator:
    """Validates customer data records before writing to DynamoDB."""
    
    REQUIRED_FIELDS = [
        "customer_id", "timestamp", "first_name", "last_name", "age", "gender",
        "purchase_id", "item", "price", "date_purchased", "customer_segment",
        "marketing_channel", "campaign_id"
    ]
    
    @staticmethod
    def validate_record(record: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a single customer record."""
        
        # Check required fields
        for field in DataValidator.REQUIRED_FIELDS:
            if field not in record:
                return False, f"Missing required field: {field}"
            
            if record[field] is None or record[field] == "":
                return False, f"Empty value for required field: {field}"
        
        # Validate data types and ranges
        try:
            # Age validation
            age = record["age"]
            if not isinstance(age, int) or age < 0 or age > 150:
                return False, f"Invalid age: {age}"
            
            # Price validation
            price = record["price"]
            if not isinstance(price, (int, float, Decimal)) or price < 0:
                return False, f"Invalid price: {price}"
            
            # Timestamp validation
            timestamp = record["timestamp"]
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Customer ID format validation
            customer_id = record["customer_id"]
            if not isinstance(customer_id, str) or len(customer_id) == 0:
                return False, f"Invalid customer_id: {customer_id}"
            
        except (ValueError, TypeError) as e:
            return False, f"Data validation error: {str(e)}"
        
        return True, None
    
    @staticmethod
    def validate_batch(records: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """Validate a batch of records and return valid records and error messages."""
        
        valid_records = []
        errors = []
        
        for i, record in enumerate(records):
            is_valid, error_msg = DataValidator.validate_record(record)
            if is_valid:
                valid_records.append(record)
            else:
                errors.append(f"Record {i}: {error_msg}")
        
        return valid_records, errors


class CustomerDataGenerator:
    """Generates realistic customer data for marketing analysis."""
    
    FIRST_NAMES = [
        "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
        "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
        "Lucas", "Harper", "Henry", "Evelyn", "Alexander", "Abigail", "Michael",
        "Emily", "Daniel", "Elizabeth", "Matthew", "Sofia", "Jackson", "Avery"
    ]
    
    LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark"
    ]
    
    ITEMS = [
        "Laptop", "Smartphone", "Tablet", "Headphones", "Smart Watch",
        "Gaming Console", "Wireless Speaker", "Camera", "Monitor", "Keyboard",
        "Mouse", "Printer", "Router", "External Drive", "Power Bank",
        "Fitness Tracker", "Smart TV", "Streaming Device", "VR Headset", "Drone"
    ]
    
    MARKETING_CHANNELS = [
        "email", "social_media", "search_ads", "display_ads", "direct_mail",
        "referral", "organic_search", "affiliate", "content_marketing", "webinar"
    ]
    
    CUSTOMER_SEGMENTS = [
        "enterprise", "small_business", "consumer", "premium", "budget",
        "tech_enthusiast", "casual_user", "professional", "student", "senior"
    ]
    
    def generate_customer_record(self, customer_id: str) -> Dict[str, Any]:
        """Generate a single customer record with purchase data."""
        
        # Generate base customer info
        first_name = random.choice(self.FIRST_NAMES)
        last_name = random.choice(self.LAST_NAMES)
        age = random.randint(18, 75)
        gender = random.choice(["Male", "Female", "Other"])
        
        # Generate purchase info
        purchase_id = str(uuid.uuid4())
        item = random.choice(self.ITEMS)
        price = Decimal(str(round(random.uniform(50.0, 2000.0), 2)))
        
        # Generate timestamp (within last 2 years)
        days_ago = random.randint(0, 730)
        purchase_date = datetime.now() - timedelta(days=days_ago)
        timestamp = purchase_date.isoformat()
        
        # Marketing attributes
        marketing_channel = random.choice(self.MARKETING_CHANNELS)
        customer_segment = random.choice(self.CUSTOMER_SEGMENTS)
        campaign_id = f"campaign_{random.randint(1000, 9999)}"
        
        return {
            "customer_id": customer_id,
            "timestamp": timestamp,
            "first_name": first_name,
            "last_name": last_name,
            "age": age,
            "gender": gender,
            "purchase_id": purchase_id,
            "item": item,
            "price": price,
            "date_purchased": purchase_date.strftime("%Y-%m-%d"),
            "customer_segment": customer_segment,
            "marketing_channel": marketing_channel,
            "campaign_id": campaign_id
        }
    
    def generate_customer_data(self, num_customers: int, purchases_per_customer: int = 3) -> List[Dict[str, Any]]:
        """Generate customer data with multiple purchases per customer."""
        
        records = []
        
        for i in range(num_customers):
            customer_id = f"customer_{i+1:06d}"
            
            # Generate multiple purchases for each customer
            for _ in range(random.randint(1, purchases_per_customer)):
                record = self.generate_customer_record(customer_id)
                records.append(record)
        
        return records


class DynamoDBPopulator:
    """Handles DynamoDB operations for populating customer data."""
    
    def __init__(self, table_name: str = "marketing-customer-data", region: str = "us-east-1"):
        self.table_name = table_name
        self.region = region
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = None
    
    def connect_to_table(self) -> bool:
        """Connect to the DynamoDB table."""
        try:
            self.table = self.dynamodb.Table(self.table_name)
            # Test connection by getting table metadata
            self.table.load()
            print(f"Connected to DynamoDB table: {self.table_name}")
            return True
        except ClientError as e:
            print(f"Error connecting to table {self.table_name}: {e}")
            return False
    
    def batch_write_records(self, records: List[Dict[str, Any]], max_retries: int = 3) -> bool:
        """Write records to DynamoDB in batches with retry logic."""
        
        if not self.table:
            print("Error: Not connected to DynamoDB table")
            return False
        
        batch_size = 25  # DynamoDB batch write limit
        total_records = len(records)
        successful_writes = 0
        failed_records = []
        
        print(f"Writing {total_records} records in batches of {batch_size}...")
        
        for i in range(0, total_records, batch_size):
            batch = records[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            # Validate batch before writing
            valid_records, validation_errors = DataValidator.validate_batch(batch)
            
            if validation_errors:
                print(f"Validation errors in batch {batch_num}:")
                for error in validation_errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(validation_errors) > 5:
                    print(f"  ... and {len(validation_errors) - 5} more errors")
                
                # Continue with valid records only
                batch = valid_records
            
            if not batch:
                print(f"Skipping batch {batch_num} - no valid records")
                continue
            
            # Retry logic for batch writing
            retry_count = 0
            batch_success = False
            
            while retry_count < max_retries and not batch_success:
                try:
                    with self.table.batch_writer() as batch_writer:
                        for record in batch:
                            batch_writer.put_item(Item=record)
                    
                    successful_writes += len(batch)
                    batch_success = True
                    progress = (successful_writes / total_records) * 100
                    print(f"Progress: {successful_writes}/{total_records} ({progress:.1f}%)")
                    
                except ClientError as e:
                    retry_count += 1
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    
                    if error_code == 'ProvisionedThroughputExceededException':
                        wait_time = 2 ** retry_count  # Exponential backoff
                        print(f"Throughput exceeded for batch {batch_num}, retrying in {wait_time}s (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        print(f"Error writing batch {batch_num} (attempt {retry_count}/{max_retries}): {e}")
                        if retry_count < max_retries:
                            time.sleep(1)
                
                except BotoCoreError as e:
                    retry_count += 1
                    print(f"Connection error for batch {batch_num} (attempt {retry_count}/{max_retries}): {e}")
                    if retry_count < max_retries:
                        time.sleep(2)
            
            if not batch_success:
                print(f"Failed to write batch {batch_num} after {max_retries} attempts")
                failed_records.extend(batch)
        
        if failed_records:
            print(f"Warning: {len(failed_records)} records failed to write")
            self._save_failed_records(failed_records)
        
        print(f"Successfully wrote {successful_writes} records to {self.table_name}")
        return len(failed_records) == 0
    
    def _save_failed_records(self, failed_records: List[Dict[str, Any]]) -> None:
        """Save failed records to a JSON file for manual review."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failed_records_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(failed_records, f, indent=2, default=str)
            print(f"Failed records saved to: {filename}")
        except Exception as e:
            print(f"Error saving failed records: {e}")
    
    def validate_data(self, sample_size: int = 5) -> bool:
        """Validate that data was written correctly by sampling records."""
        
        if not self.table:
            return False
        
        try:
            # Get table item count
            response = self.table.describe_table()
            item_count = response['Table']['ItemCount']
            print(f"\nTable statistics:")
            print(f"  Total items: {item_count}")
            print(f"  Table status: {response['Table']['TableStatus']}")
            
            # Scan a small sample of records
            scan_response = self.table.scan(Limit=sample_size)
            items = scan_response.get('Items', [])
            
            if not items:
                print("Warning: No items found in table scan")
                return False
            
            print(f"\nValidation: Scanned {len(items)} sample records")
            
            # Validate sample records
            valid_count = 0
            for item in items:
                is_valid, error_msg = DataValidator.validate_record(item)
                if is_valid:
                    valid_count += 1
                else:
                    print(f"Invalid record found: {error_msg}")
            
            print(f"Valid records in sample: {valid_count}/{len(items)}")
            
            # Show sample record
            print("\nSample record:")
            print(json.dumps(items[0], indent=2, default=str))
            
            # Test GSI queries
            self._test_gsi_queries()
            
            return valid_count == len(items)
            
        except ClientError as e:
            print(f"Error validating data: {e}")
            return False
    
    def _test_gsi_queries(self) -> None:
        """Test Global Secondary Index queries."""
        
        try:
            # Test marketing channel index
            response = self.table.query(
                IndexName='marketing-channel-index',
                KeyConditionExpression='marketing_channel = :channel',
                ExpressionAttributeValues={':channel': 'email'},
                Limit=1
            )
            
            email_count = response['Count']
            print(f"GSI Test - Email marketing records: {email_count}")
            
            # Test customer segment index
            response = self.table.query(
                IndexName='customer-segment-index',
                KeyConditionExpression='customer_segment = :segment',
                ExpressionAttributeValues={':segment': 'enterprise'},
                Limit=1
            )
            
            enterprise_count = response['Count']
            print(f"GSI Test - Enterprise segment records: {enterprise_count}")
            
        except ClientError as e:
            print(f"GSI query test failed: {e}")


def main():
    """Main function to populate DynamoDB with customer data."""
    
    parser = argparse.ArgumentParser(description="Populate DynamoDB with customer data")
    parser.add_argument("--table-name", default="marketing-customer-data",
                       help="DynamoDB table name (default: marketing-customer-data)")
    parser.add_argument("--region", default="us-east-1",
                       help="AWS region (default: us-east-1)")
    parser.add_argument("--customers", type=int, default=1000,
                       help="Number of customers to generate (default: 1000)")
    parser.add_argument("--max-purchases", type=int, default=5,
                       help="Maximum purchases per customer (default: 5)")
    parser.add_argument("--validate", action="store_true",
                       help="Validate data after writing")
    parser.add_argument("--dry-run", action="store_true",
                       help="Generate and validate data without writing to DynamoDB")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Maximum retries for failed batch writes (default: 3)")
    
    args = parser.parse_args()
    
    print("Marketing Research Agent - DynamoDB Data Population")
    print("=" * 50)
    print(f"Table: {args.table_name}")
    print(f"Region: {args.region}")
    print(f"Customers: {args.customers}")
    print(f"Max purchases per customer: {args.max_purchases}")
    print()
    
    # Generate customer data
    print("Generating customer data...")
    generator = CustomerDataGenerator()
    records = generator.generate_customer_data(args.customers, args.max_purchases)
    print(f"Generated {len(records)} total records")
    
    # Validate generated data
    print("Validating generated data...")
    valid_records, validation_errors = DataValidator.validate_batch(records)
    
    if validation_errors:
        print(f"Found {len(validation_errors)} validation errors:")
        for error in validation_errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(validation_errors) > 10:
            print(f"  ... and {len(validation_errors) - 10} more errors")
        
        if len(valid_records) == 0:
            print("No valid records generated. Exiting.")
            sys.exit(1)
        
        print(f"Proceeding with {len(valid_records)} valid records")
        records = valid_records
    
    # Dry run mode - just validate and exit
    if args.dry_run:
        print(f"\nDry run completed successfully!")
        print(f"Generated {len(records)} valid records")
        print("Use --validate flag without --dry-run to write to DynamoDB")
        return
    
    # Connect to DynamoDB and populate data
    populator = DynamoDBPopulator(args.table_name, args.region)
    
    if not populator.connect_to_table():
        print("Failed to connect to DynamoDB table")
        print("Make sure:")
        print("1. AWS credentials are configured")
        print("2. The table exists in the specified region")
        print("3. You have the necessary IAM permissions")
        sys.exit(1)
    
    if not populator.batch_write_records(records, args.max_retries):
        print("Some records failed to write to DynamoDB")
        print("Check the failed_records_*.json file for details")
        # Don't exit with error - partial success is still useful
    
    # Validate data if requested
    if args.validate:
        print("\nValidating written data...")
        if not populator.validate_data():
            print("Data validation failed")
            sys.exit(1)
    
    print("\nData population completed!")


if __name__ == "__main__":
    main()