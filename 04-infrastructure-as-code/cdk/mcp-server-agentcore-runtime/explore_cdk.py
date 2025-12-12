#!/usr/bin/env python3

import aws_cdk.aws_bedrockagentcore as bedrockagentcore
import inspect

print("=== Exploring aws_cdk.aws_bedrockagentcore module ===")
print()

# List all attributes in the module
print("Available classes and functions:")
for name in dir(bedrockagentcore):
    if not name.startswith('_'):
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print()
print("=== CfnRuntime class details ===")

# Explore CfnRuntime class
runtime_class = bedrockagentcore.CfnRuntime
print(f"CfnRuntime: {runtime_class}")

print("\nCfnRuntime attributes:")
for name in dir(runtime_class):
    if not name.startswith('_'):
        try:
            attr = getattr(runtime_class, name)
            print(f"  {name}: {type(attr)}")
        except Exception as e:
            print(f"  {name}: Error accessing - {e}")

print("\nLooking for Property classes:")
for name in dir(bedrockagentcore):
    if 'Property' in name:
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print("\nLooking for Authorizer related classes:")
for name in dir(bedrockagentcore):
    if 'Auth' in name.lower():
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

print("\nLooking for JWT related classes:")
for name in dir(bedrockagentcore):
    if 'jwt' in name.lower() or 'JWT' in name:
        obj = getattr(bedrockagentcore, name)
        print(f"  {name}: {type(obj)}")

# Try to get the constructor signature
print("\n=== CfnRuntime constructor signature ===")
try:
    sig = inspect.signature(runtime_class.__init__)
    print(f"Constructor signature: {sig}")
except Exception as e:
    print(f"Error getting signature: {e}")

# Try to explore the CfnRuntime properties
print("\n=== Trying to find nested property classes ===")
try:
    # Check if there are nested classes
    for name in dir(runtime_class):
        if not name.startswith('_') and name.endswith('Property'):
            prop_class = getattr(runtime_class, name)
            print(f"  {name}: {prop_class}")
            
            # Try to get the constructor signature
            try:
                prop_sig = inspect.signature(prop_class.__init__)
                print(f"    Constructor: {prop_sig}")
            except Exception as e:
                print(f"    Error getting constructor: {e}")
                
except Exception as e:
    print(f"Error exploring nested classes: {e}")
