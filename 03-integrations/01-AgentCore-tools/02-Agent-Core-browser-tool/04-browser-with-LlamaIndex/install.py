#!/usr/bin/env python3
"""
Installation script for llamaindex-agentcore-browser-integration.

This script provides automated installation with environment detection,
dependency management, and configuration setup.
"""

import sys
import subprocess
import os
import platform
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Minimum Python version required
MIN_PYTHON_VERSION = (3, 12)
MAX_PYTHON_VERSION = (3, 12)

class InstallationError(Exception):
    """Custom exception for installation errors."""
    pass

class Installer:
    """Main installer class for the package."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.root_dir = Path(__file__).parent
        self.python_executable = sys.executable
        
    def log(self, message: str, level: str = "INFO") -> None:
        """Log installation messages."""
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{level}] {message}")
    
    def check_python_version(self) -> None:
        """Check if Python version is compatible."""
        current_version = sys.version_info[:2]
        
        if current_version < MIN_PYTHON_VERSION:
            raise InstallationError(
                f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required, "
                f"but {current_version[0]}.{current_version[1]} found"
            )
        
        if current_version > MAX_PYTHON_VERSION:
            self.log(
                f"Python {current_version[0]}.{current_version[1]} detected. "
                f"This package is tested with Python {MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}",
                "WARNING"
            )
        
        self.log(f"Python version {current_version[0]}.{current_version[1]} is compatible")
    
    def check_system_requirements(self) -> Dict[str, str]:
        """Check system requirements and return system info."""
        system_info = {
            "platform": platform.system(),
            "architecture": platform.machine(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "pip_version": self._get_pip_version()
        }
        
        self.log(f"System: {system_info['platform']} {system_info['architecture']}")
        self.log(f"Python: {system_info['python_version']}")
        self.log(f"Pip: {system_info['pip_version']}")
        
        return system_info
    
    def _get_pip_version(self) -> str:
        """Get pip version."""
        try:
            result = subprocess.run(
                [self.python_executable, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.split()[1]
        except subprocess.CalledProcessError:
            return "unknown"
    
    def upgrade_pip(self) -> None:
        """Upgrade pip to latest version."""
        self.log("Upgrading pip...")
        try:
            subprocess.run(
                [self.python_executable, "-m", "pip", "install", "--upgrade", "pip"],
                check=True,
                capture_output=not self.verbose
            )
            self.log("Pip upgraded successfully")
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to upgrade pip: {e}")
    
    def install_dependencies(self, environment: str = "dev") -> None:
        """Install package dependencies."""
        requirements_files = {
            "prod": "requirements-prod.txt",
            "dev": "requirements-dev.txt",
            "base": "requirements.txt"
        }
        
        req_file = requirements_files.get(environment, "requirements.txt")
        req_path = self.root_dir / req_file
        
        if not req_path.exists():
            raise InstallationError(f"Requirements file not found: {req_path}")
        
        self.log(f"Installing {environment} dependencies from {req_file}...")
        
        try:
            cmd = [
                self.python_executable, "-m", "pip", "install",
                "-r", str(req_path),
                "--upgrade"
            ]
            
            if not self.verbose:
                cmd.append("--quiet")
            
            subprocess.run(cmd, check=True)
            self.log(f"Dependencies installed successfully")
            
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install dependencies: {e}")
    
    def install_package(self, editable: bool = True) -> None:
        """Install the package itself."""
        self.log("Installing package...")
        
        try:
            cmd = [self.python_executable, "-m", "pip", "install"]
            
            if editable:
                cmd.extend(["-e", "."])
            else:
                cmd.append(".")
            
            if not self.verbose:
                cmd.append("--quiet")
            
            subprocess.run(cmd, cwd=self.root_dir, check=True)
            self.log("Package installed successfully")
            
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install package: {e}")
    
    def setup_pre_commit(self) -> None:
        """Set up pre-commit hooks."""
        self.log("Setting up pre-commit hooks...")
        
        try:
            # Install pre-commit hooks
            subprocess.run(
                [self.python_executable, "-m", "pre_commit", "install"],
                cwd=self.root_dir,
                check=True,
                capture_output=not self.verbose
            )
            self.log("Pre-commit hooks installed successfully")
            
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to install pre-commit hooks: {e}", "WARNING")
    
    def create_config_template(self) -> None:
        """Create configuration template if it doesn't exist."""
        config_template = self.root_dir / "config.example.yaml"
        config_file = self.root_dir / "config.yaml"
        
        if config_template.exists() and not config_file.exists():
            self.log("Creating configuration file from template...")
            try:
                import shutil
                shutil.copy2(config_template, config_file)
                self.log(f"Configuration template created: {config_file}")
                self.log("Please edit config.yaml with your specific settings")
            except Exception as e:
                self.log(f"Failed to create config template: {e}", "WARNING")
    
    def verify_installation(self) -> bool:
        """Verify that installation was successful."""
        self.log("Verifying installation...")
        
        try:
            # Try to import the main package
            result = subprocess.run(
                [self.python_executable, "-c", 
                 "import llamaindex_agentcore_integration; print('Import successful')"],
                capture_output=True,
                text=True,
                check=True
            )
            
            if "Import successful" in result.stdout:
                self.log("Installation verification successful")
                return True
            else:
                self.log("Installation verification failed", "ERROR")
                return False
                
        except subprocess.CalledProcessError as e:
            self.log(f"Installation verification failed: {e}", "ERROR")
            return False
    
    def run_tests(self) -> bool:
        """Run basic tests to verify functionality."""
        self.log("Running basic tests...")
        
        try:
            result = subprocess.run(
                [self.python_executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                cwd=self.root_dir,
                capture_output=not self.verbose,
                check=True
            )
            
            self.log("Basic tests passed")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Tests failed: {e}", "WARNING")
            return False
    
    def install(self, 
                environment: str = "dev",
                editable: bool = True,
                skip_tests: bool = False,
                setup_hooks: bool = True) -> None:
        """Run complete installation process."""
        try:
            self.log("Starting installation process...")
            
            # Check requirements
            self.check_python_version()
            system_info = self.check_system_requirements()
            
            # Upgrade pip
            self.upgrade_pip()
            
            # Install dependencies
            self.install_dependencies(environment)
            
            # Install package
            self.install_package(editable)
            
            # Setup development tools
            if environment == "dev" and setup_hooks:
                self.setup_pre_commit()
            
            # Create config template
            self.create_config_template()
            
            # Verify installation
            if not self.verify_installation():
                raise InstallationError("Installation verification failed")
            
            # Run tests
            if not skip_tests and environment == "dev":
                self.run_tests()
            
            self.log("Installation completed successfully!")
            self._print_next_steps()
            
        except InstallationError as e:
            self.log(f"Installation failed: {e}", "ERROR")
            sys.exit(1)
        except Exception as e:
            self.log(f"Unexpected error during installation: {e}", "ERROR")
            sys.exit(1)
    
    def _print_next_steps(self) -> None:
        """Print next steps for the user."""
        print("\n" + "="*60)
        print("INSTALLATION COMPLETE!")
        print("="*60)
        print("\nNext steps:")
        print("1. Edit config.yaml with your AWS credentials and settings")
        print("2. Run: python -c 'import llamaindex_agentcore_integration; print(\"Ready!\")'")
        print("3. Check out examples/ directory for usage examples")
        print("4. Read docs/README.md for detailed documentation")
        print("\nFor help:")
        print("- GitHub: https://github.com/aws-samples/agentcore-samples")
        print("- Documentation: https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html")
        print("="*60)

def main():
    """Main installation entry point."""
    parser = argparse.ArgumentParser(
        description="Install llamaindex-agentcore-browser-integration"
    )
    parser.add_argument(
        "--environment", "-e",
        choices=["dev", "prod", "base"],
        default="dev",
        help="Installation environment (default: dev)"
    )
    parser.add_argument(
        "--no-editable",
        action="store_true",
        help="Install package in non-editable mode"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true", 
        help="Skip running tests after installation"
    )
    parser.add_argument(
        "--no-hooks",
        action="store_true",
        help="Skip setting up pre-commit hooks"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    installer = Installer(verbose=args.verbose)
    installer.install(
        environment=args.environment,
        editable=not args.no_editable,
        skip_tests=args.skip_tests,
        setup_hooks=not args.no_hooks
    )

if __name__ == "__main__":
    main()