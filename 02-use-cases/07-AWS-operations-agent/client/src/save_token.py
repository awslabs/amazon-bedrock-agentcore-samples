#!/usr/bin/env python3
"""
Simple script to save Okta token to a file
"""

import os
import sys

def save_token():
    """Save token to file"""
    print("Enter your Okta token (paste it and press Enter):")
    token = input().strip()
    
    if not token:
        print("No token provided. Exiting.")
        return
    
    # Default file path
    file_path = os.path.expanduser("~/.okta_token")
    
    # Use command line argument if provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    try:
        with open(file_path, 'w') as f:
            f.write(token)
        print(f"✅ Token saved to {file_path}")
        print(f"You can now use it with: /token-file {file_path}")
    except Exception as e:
        print(f"❌ Error saving token: {str(e)}")

if __name__ == "__main__":
    save_token()
