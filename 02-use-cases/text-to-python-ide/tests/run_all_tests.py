#!/usr/bin/env python3
"""
Comprehensive Test Suite for AgentCore Code Interpreter
"""

import os
import sys
import subprocess
import time
import requests
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'backend'))

class TestRunner:
    def __init__(self):
        self.backend_pid = None
        self.frontend_pid = None
        self.passed_tests = 0
        self.total_tests = 0
        
    def start_backend(self):
        """Start the backend server"""
        print("🚀 Starting backend server...")
        
        # Kill existing backend
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
        time.sleep(2)
        
        # Start backend
        backend_process = subprocess.Popen(
            [sys.executable, "backend/main.py"],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.backend_pid = backend_process.pid
        
        # Wait for backend to start
        for i in range(30):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Backend started successfully")
                    return True
            except:
                time.sleep(1)
        
        print("❌ Backend failed to start")
        return False
    
    def stop_backend(self):
        """Stop the backend server"""
        if self.backend_pid:
            try:
                os.kill(self.backend_pid, 9)
                print("✅ Backend stopped")
            except:
                pass
        os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
    
    def run_test(self, test_name, test_func):
        """Run a single test"""
        print(f"\n📋 Running {test_name}...")
        print("-" * 50)
        
        self.total_tests += 1
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                self.passed_tests += 1
                return True
            else:
                print(f"❌ {test_name} FAILED")
                return False
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
            return False
    
    def test_environment_setup(self):
        """Test environment and dependencies"""
        print("🔍 Testing Environment Setup")
        
        # Check virtual environment
        if not os.path.exists(project_root / "venv"):
            print("❌ Virtual environment not found")
            return False
        
        # Check AWS credentials
        try:
            from main import setup_aws_credentials
            aws_session, aws_region = setup_aws_credentials()
            if aws_session and aws_region:
                print("✅ AWS credentials configured")
            else:
                print("❌ AWS credentials not configured")
                return False
        except Exception as e:
            print(f"❌ AWS setup failed: {e}")
            return False
        
        # Check dependencies
        try:
            import strands
            import bedrock_agentcore
            print("✅ Core dependencies available")
        except ImportError as e:
            print(f"❌ Missing dependency: {e}")
            return False
        
        return True
    
    def test_model_initialization(self):
        """Test model initialization and fallback"""
        print("🤖 Testing Model Initialization")
        
        try:
            from main import create_bedrock_model_with_fallback
            
            model, model_id = create_bedrock_model_with_fallback('us-east-1')
            
            print(f"✅ Model initialized: {model_id}")
            
            if model_id.startswith('us.'):
                print("✅ Using inference profile")
            else:
                print("⚠️  Using standard model")
            
            return True
        except Exception as e:
            print(f"❌ Model initialization failed: {e}")
            return False
    
    def test_agent_initialization(self):
        """Test agent initialization"""
        print("🤖 Testing Agent Initialization")
        
        try:
            from main import setup_aws_credentials, initialize_agents
            import main
            
            # Setup AWS
            aws_session, aws_region = setup_aws_credentials()
            main.aws_session = aws_session
            main.aws_region = aws_region
            
            # Initialize agents
            initialize_agents()
            
            if hasattr(main, 'code_generator_agent') and main.code_generator_agent:
                print("✅ Code generator agent initialized")
            else:
                print("❌ Code generator agent not initialized")
                return False
            
            if hasattr(main, 'code_executor_agent'):
                print("✅ Code executor agent initialized")
            else:
                print("❌ Code executor agent not initialized")
                return False
            
            return True
        except Exception as e:
            print(f"❌ Agent initialization failed: {e}")
            return False
    
    def test_code_generation_api(self):
        """Test code generation API"""
        print("🔧 Testing Code Generation API")
        
        try:
            response = requests.post(
                "http://localhost:8000/api/generate-code",
                json={"prompt": "Create a function to calculate factorial"},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ API returned status {response.status_code}")
                return False
            
            data = response.json()
            code = data.get("code", "")
            
            if not isinstance(code, str):
                print(f"❌ Code is not a string: {type(code)}")
                return False
            
            if len(code.strip()) == 0:
                print("❌ Generated code is empty")
                return False
            
            print(f"✅ Generated {len(code)} characters of code")
            return True
            
        except Exception as e:
            print(f"❌ Code generation test failed: {e}")
            return False
    
    def test_code_execution_api(self):
        """Test code execution API"""
        print("⚡ Testing Code Execution API")
        
        test_code = """
print("Hello, World!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""
        
        try:
            response = requests.post(
                "http://localhost:8000/api/execute-code",
                json={"code": test_code.strip()},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ API returned status {response.status_code}")
                return False
            
            data = response.json()
            result = data.get("result", "")
            
            if not isinstance(result, str):
                print(f"❌ Result is not a string: {type(result)}")
                return False
            
            if len(result.strip()) == 0:
                print("❌ Execution result is empty")
                return False
            
            print(f"✅ Execution completed with {len(result)} characters of output")
            return True
            
        except Exception as e:
            print(f"❌ Code execution test failed: {e}")
            return False
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        print("🏥 Testing Health Endpoint")
        
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            
            if response.status_code != 200:
                print(f"❌ Health check returned status {response.status_code}")
                return False
            
            data = response.json()
            
            if data.get("status") != "healthy":
                print(f"❌ System not healthy: {data.get('status')}")
                return False
            
            print(f"✅ System healthy with model: {data.get('current_model', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def test_agentcore_integration(self):
        """Test AgentCore integration"""
        print("🔗 Testing AgentCore Integration")
        
        try:
            from bedrock_agentcore.tools.code_interpreter_client import code_session
            
            with code_session('us-east-1') as code_client:
                response = code_client.invoke('executeCode', {
                    'code': 'print("AgentCore test successful")',
                    'language': 'python',
                    'clearContext': True
                })
                
                print("✅ AgentCore integration working")
                return True
                
        except Exception as e:
            print(f"❌ AgentCore integration failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("🎯 AgentCore Code Interpreter - Comprehensive Test Suite")
        print("=" * 70)
        
        # Environment tests (don't need backend)
        tests_no_backend = [
            ("Environment Setup", self.test_environment_setup),
            ("Model Initialization", self.test_model_initialization),
            ("Agent Initialization", self.test_agent_initialization),
            ("AgentCore Integration", self.test_agentcore_integration)
        ]
        
        for test_name, test_func in tests_no_backend:
            self.run_test(test_name, test_func)
        
        # Start backend for API tests
        if not self.start_backend():
            print("❌ Cannot run API tests without backend")
            return self.passed_tests, self.total_tests
        
        # API tests (need backend)
        tests_with_backend = [
            ("Health Endpoint", self.test_health_endpoint),
            ("Code Generation API", self.test_code_generation_api),
            ("Code Execution API", self.test_code_execution_api)
        ]
        
        for test_name, test_func in tests_with_backend:
            self.run_test(test_name, test_func)
        
        return self.passed_tests, self.total_tests
    
    def cleanup(self):
        """Cleanup resources"""
        print("\n🧹 Cleaning up...")
        self.stop_backend()

def main():
    """Main test runner"""
    runner = TestRunner()
    
    try:
        passed, total = runner.run_all_tests()
        
        print("\n" + "=" * 70)
        print(f"🎯 TEST RESULTS: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Application is ready for use.")
            return 0
        else:
            print("❌ Some tests failed. Check the output above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test suite error: {e}")
        return 1
    finally:
        runner.cleanup()

if __name__ == "__main__":
    sys.exit(main())
