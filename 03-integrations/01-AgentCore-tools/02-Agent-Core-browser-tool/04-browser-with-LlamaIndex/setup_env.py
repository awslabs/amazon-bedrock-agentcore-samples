#!/usr/bin/env python3.12
"""
Environment setup script for LlamaIndex-AgentCore browser tool integration.
This script sets up a Python 3.12 virtual environment with all required dependencies.
"""

import sys
import subprocess
import venv
from pathlib import Path
import os

def check_python_version():
    """Check if we're running Python 3.12+."""
    if sys.version_info < (3, 12):
        print(f"❌ Python 3.12+ required, got {sys.version}")
        print("Please install Python 3.12 and run this script with python3.12")
        return False
    
    print(f"✅ Using Python {sys.version}")
    return True

def create_virtual_environment(venv_path: Path):
    """Create a Python 3.12 virtual environment."""
    print(f"🔧 Creating virtual environment at {venv_path}")
    
    try:
        venv.create(venv_path, with_pip=True, clear=True)
        print("✅ Virtual environment created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False

def get_venv_python(venv_path: Path) -> Path:
    """Get the path to the Python executable in the virtual environment."""
    if os.name == 'nt':  # Windows
        return venv_path / "Scripts" / "python.exe"
    else:  # Unix/Linux/macOS
        return venv_path / "bin" / "python"

def install_dependencies(venv_python: Path, requirements_file: Path):
    """Install dependencies in the virtual environment."""
    print(f"📦 Installing dependencies from {requirements_file}")
    
    try:
        # Upgrade pip first
        subprocess.run([
            str(venv_python), "-m", "pip", "install", "--upgrade", "pip"
        ], check=True, capture_output=True, text=True)
        
        # Install requirements
        result = subprocess.run([
            str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)
        ], check=True, capture_output=True, text=True)
        
        print("✅ Dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def verify_installation(venv_python: Path):
    """Verify the installation by running basic tests."""
    print("🧪 Verifying installation...")
    
    try:
        # Test basic Python functionality
        test_script = '''
import sys
print(f"Python version: {sys.version}")

# Test that we can import basic modules
try:
    import asyncio
    import pathlib
    import dataclasses
    import enum
    print("✅ Basic modules imported successfully")
except ImportError as e:
    print(f"❌ Failed to import basic modules: {e}")
    sys.exit(1)

print("🎉 Installation verification completed!")
'''
        
        result = subprocess.run([
            str(venv_python), "-c", test_script
        ], check=True, capture_output=True, text=True)
        
        print(result.stdout)
        print("✅ Installation verified successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation verification failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False

def create_activation_script(venv_path: Path, project_root: Path):
    """Create a convenient activation script."""
    if os.name == 'nt':  # Windows
        activate_script = venv_path / "Scripts" / "activate.bat"
        script_content = f'''@echo off
call "{activate_script}"
echo "✅ LlamaIndex-AgentCore Python 3.12 environment activated"
echo "📁 Project root: {project_root}"
echo "🐍 Python: {get_venv_python(venv_path)}"
'''
        script_path = project_root / "activate_env.bat"
    else:  # Unix/Linux/macOS
        activate_script = venv_path / "bin" / "activate"
        script_content = f'''#!/bin/bash
source "{activate_script}"
echo "✅ LlamaIndex-AgentCore Python 3.12 environment activated"
echo "📁 Project root: {project_root}"
echo "🐍 Python: {get_venv_python(venv_path)}"
'''
        script_path = project_root / "activate_env.sh"
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        if os.name != 'nt':
            os.chmod(script_path, 0o755)  # Make executable on Unix systems
        
        print(f"✅ Activation script created: {script_path}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create activation script: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 Setting up LlamaIndex-AgentCore Python 3.12 environment...")
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Get project paths
    project_root = Path(__file__).parent
    venv_path = project_root / "venv"
    requirements_file = project_root / "requirements.txt"
    
    print(f"📁 Project root: {project_root}")
    print(f"📁 Virtual environment: {venv_path}")
    print(f"📄 Requirements file: {requirements_file}")
    
    # Check if requirements file exists
    if not requirements_file.exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        return False
    
    # Create virtual environment
    if not create_virtual_environment(venv_path):
        return False
    
    # Get virtual environment Python
    venv_python = get_venv_python(venv_path)
    print(f"🐍 Virtual environment Python: {venv_python}")
    
    # Install dependencies
    if not install_dependencies(venv_python, requirements_file):
        return False
    
    # Verify installation
    if not verify_installation(venv_python):
        return False
    
    # Create activation script
    if not create_activation_script(venv_path, project_root):
        return False
    
    print("\n🎉 Environment setup completed successfully!")
    print("\n📋 Next steps:")
    print(f"1. Activate the environment:")
    if os.name == 'nt':
        print(f"   .\\activate_env.bat")
    else:
        print(f"   source ./activate_env.sh")
    print(f"2. Run tests:")
    print(f"   python test_python312.py")
    print(f"3. Start development!")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)