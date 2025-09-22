#!/usr/bin/env python3
"""
Test script for Claude Code headless mode
"""

import json
import subprocess
import sys

def test_headless_mode():
    """Test Claude Code in headless mode"""
    
    # Test prompts
    test_cases = [
        {
            "name": "Simple Hello World",
            "prompt": "Create a Python script that prints 'Hello, World!'"
        },
        {
            "name": "Function Generation",
            "prompt": "Create a Python function that calculates the factorial of a number"
        },
        {
            "name": "Class Creation",
            "prompt": "Create a Python class for a simple to-do list with add, remove, and list methods"
        }
    ]
    
    print("🧪 Testing Claude Code Headless Mode")
    print("=" * 50)
    
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"   Prompt: {test['prompt'][:50]}...")
        
        # Construct the command
        payload = json.dumps({"prompt": test['prompt']})
        cmd = f"echo '{payload}' | claude -p --output-format json"
        
        try:
            # Run the command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    if response.get('is_error'):
                        print(f"   ❌ Error: {response.get('result', 'Unknown error')}")
                    else:
                        print(f"   ✅ Success!")
                        print(f"   💰 Cost: ${response.get('total_cost_usd', 0):.4f}")
                        print(f"   ⏱️  Duration: {response.get('duration_ms', 0)/1000:.2f}s")
                except json.JSONDecodeError:
                    print(f"   ⚠️  Non-JSON response: {result.stdout[:100]}...")
            else:
                print(f"   ❌ Command failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  Timeout after 60 seconds")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("✅ Testing complete!")

if __name__ == "__main__":
    # Check if Claude Code is installed
    try:
        subprocess.run(["claude", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Claude Code CLI not found. Please install it first:")
        print("   npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
    
    test_headless_mode()
