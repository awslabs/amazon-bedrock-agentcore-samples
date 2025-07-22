#!/usr/bin/env python3
"""
Test script to verify model fallback logic
"""

import os
import sys
from dotenv import load_dotenv

def test_model_availability():
    """Test which models are available in the current region"""
    print("🔍 Testing Model Availability")
    print("=" * 50)
    
    load_dotenv()
    
    import boto3
    
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    print(f"Region: {aws_region}")
    
    try:
        session = boto3.Session()
        bedrock_client = session.client('bedrock', region_name=aws_region)
        
        response = bedrock_client.list_foundation_models()
        available_models = [model['modelId'] for model in response.get('modelSummaries', [])]
        
        # Test models in priority order
        test_models = [
            ("Claude Sonnet 4", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            ("Nova Premier", "us.amazon.nova-premier-v1:0"),
            ("Claude 3.5 Sonnet", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        ]
        
        print(f"\nFound {len(available_models)} total models in {aws_region}")
        print("\nTesting priority models:")
        
        for name, model_id in test_models:
            if model_id in available_models:
                print(f"✅ {name}: {model_id} - AVAILABLE")
            else:
                print(f"❌ {name}: {model_id} - NOT AVAILABLE")
        
        return available_models
        
    except Exception as e:
        print(f"❌ Failed to list models: {e}")
        return []

def test_model_fallback_logic():
    """Test the model fallback logic"""
    print("\n🧪 Testing Model Fallback Logic")
    print("=" * 50)
    
    try:
        sys.path.append('backend')
        from main import create_bedrock_model_with_fallback
        
        load_dotenv()
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        
        model, model_id = create_bedrock_model_with_fallback(aws_region)
        
        print(f"✅ Selected model: {model_id}")
        print(f"✅ Model object created successfully")
        
        return model, model_id
        
    except Exception as e:
        print(f"❌ Model fallback test failed: {e}")
        return None, None

def test_agent_initialization():
    """Test agent initialization with fallback model"""
    print("\n🤖 Testing Agent Initialization")
    print("=" * 50)
    
    try:
        sys.path.append('backend')
        from main import setup_aws_credentials, initialize_agents
        
        # Setup AWS
        aws_session, aws_region = setup_aws_credentials()
        
        # Initialize agents
        import main
        main.aws_session = aws_session
        main.aws_region = aws_region
        initialize_agents()
        
        current_model = getattr(main, 'current_model_id', 'Unknown')
        print(f"✅ Agents initialized with model: {current_model}")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return False

def main():
    """Run all model fallback tests"""
    print("🎯 Model Fallback Testing")
    print("=" * 60)
    
    # Test 1: Check model availability
    available_models = test_model_availability()
    
    # Test 2: Test fallback logic
    model, model_id = test_model_fallback_logic()
    
    # Test 3: Test agent initialization
    agent_success = test_agent_initialization()
    
    print("\n🎯 SUMMARY")
    print("=" * 30)
    
    if model_id:
        print(f"✅ Selected Model: {model_id}")
        
        if "claude-sonnet-4" in model_id:
            print("🎉 Using PRIMARY model: Claude Sonnet 4")
        elif "nova-premier" in model_id:
            print("⚠️  Using FALLBACK model: Nova Premier")
        elif "claude-3-5-sonnet" in model_id:
            print("⚠️  Using LAST RESORT model: Claude 3.5 Sonnet")
        else:
            print(f"❓ Using UNKNOWN model: {model_id}")
    
    if agent_success:
        print("✅ Agents initialized successfully")
    else:
        print("❌ Agent initialization failed")
    
    print(f"\n📊 Models available in region: {len(available_models)}")
    
    return 0 if model_id and agent_success else 1

if __name__ == "__main__":
    sys.exit(main())
