"""
Data loader for insurance API - loads data from the data folder
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

class InsuranceDataLoader:
    def __init__(self, data_path: str = None):
        """Initialize data loader with path to data directory"""
        if data_path is None:
            # Default to data folder in parent directory
            current_dir = Path(__file__).parent
            self.data_path = current_dir.parent / "data"
        else:
            self.data_path = Path(data_path)
        
        self._customers = None
        self._credit_reports = None
        self._vehicles = None
        self._products = None
        self._pricing_rules = None
        self._policies = None
        
    def _load_json_file(self, filename: str) -> Dict:
        """Load JSON file from data directory"""
        file_path = self.data_path / filename
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                print(f"Successfully loaded {filename} with {len(str(data))} characters")
                return data
        except FileNotFoundError:
            print(f"Warning: {filename} not found at {file_path}")
            # Try alternative paths
            alternative_paths = [
                Path("/opt/data") / filename,  # Lambda /opt directory
                Path("./data") / filename,     # Current directory
                Path("../data") / filename,    # Parent directory
                Path("/tmp/data") / filename,  # Lambda tmp directory
                Path("/var/task/data") / filename,  # Lambda task directory
            ]
            for alt_path in alternative_paths:
                try:
                    with open(alt_path, 'r') as f:
                        data = json.load(f)
                        print(f"Found {filename} at alternative path: {alt_path}")
                        return data
                except:
                    continue
            print(f"Could not find {filename} in any location")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing {filename}: {e}")
            return {}
    
    @property
    def customers(self) -> List[Dict]:
        """Get customers data"""
        if self._customers is None:
            data = self._load_json_file("customers.json")
            self._customers = data.get("customers", [])
        return self._customers
    
    @property
    def credit_reports(self) -> List[Dict]:
        """Get credit reports data"""
        if self._credit_reports is None:
            data = self._load_json_file("credit_reports.json")
            self._credit_reports = data.get("reports", [])
        return self._credit_reports
    
    @property
    def vehicles(self) -> List[Dict]:
        """Get vehicles data"""
        if self._vehicles is None:
            data = self._load_json_file("vehicles.json")
            self._vehicles = data.get("vehicles", [])
        return self._vehicles
    
    @property
    def products(self) -> Dict:
        """Get products data"""
        if self._products is None:
            self._products = self._load_json_file("products.json")
        return self._products
    
    @property
    def pricing_rules(self) -> Dict:
        """Get pricing rules data"""
        if self._pricing_rules is None:
            self._pricing_rules = self._load_json_file("pricing_rules.json")
        return self._pricing_rules
    
    @property
    def policies(self) -> Dict:
        """Get policies data"""
        if self._policies is None:
            self._policies = self._load_json_file("policies.json")
        return self._policies
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict]:
        """Get customer by ID"""
        for customer in self.customers:
            if customer.get("id") == customer_id:
                return customer
        return None
    
    def get_credit_report_by_customer_id(self, customer_id: str) -> Optional[Dict]:
        """Get credit report by customer ID"""
        for report in self.credit_reports:
            if report.get("customer_id") == customer_id:
                return report
        return None
    
    def get_vehicle_info(self, make: str, model: str, year: str) -> Optional[Dict]:
        """Get vehicle information by make, model, year"""
        year_int = int(year)
        for vehicle in self.vehicles:
            if (vehicle.get("make", "").lower() == make.lower() and 
                vehicle.get("model", "").lower() == model.lower() and
                year_int in vehicle.get("years", [])):
                
                # Create vehicle info with year-specific data
                vehicle_info = vehicle.copy()
                vehicle_info["year"] = year
                vehicle_info["value"] = vehicle.get("base_value", {}).get(str(year), 25000)
                vehicle_info["current_value"] = int(vehicle_info["value"] * 0.85)  # Depreciation
                vehicle_info["age"] = 2025 - year_int
                vehicle_info["is_new"] = year_int >= 2024
                vehicle_info["display_name"] = f"{year} {make} {model}"
                
                return vehicle_info
        return None
    
    def calculate_age_from_dob(self, dob: str) -> int:
        """Calculate age from date of birth string (YYYY-MM-DD)"""
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d")
            today = datetime.now()
            age = today.year - birth_date.year
            if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
                age -= 1
            return age
        except:
            return 30  # Default age if parsing fails
