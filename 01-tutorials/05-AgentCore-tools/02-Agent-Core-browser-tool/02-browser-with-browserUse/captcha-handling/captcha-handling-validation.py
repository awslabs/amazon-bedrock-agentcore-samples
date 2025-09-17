#!/usr/bin/env python3
"""
CAPTCHA Handling Tutorial - Validation Framework

This notebook provides comprehensive validation for the AgentCore Browser Tool + browser-use
CAPTCHA handling tutorial, ensuring students have successfully completed each section
and mastered the key integration concepts.

Requirements: 6.1, 6.2, 6.4
"""

import sys
import os
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Rich console for beautiful output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich.syntax import Syntax

# Add current directory to path for imports
sys.path.append(os.getcwd())

console = Console()
console.print("[bold green]✅ Validation Framework Initialized[/bold green]")

@dataclass
class ValidationResult:
    """Result of a validation check"""
    section: str
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None

@dataclass
class SectionProgress:
    """Progress tracking for a tutorial section"""
    section_number: int
    section_name: str
    completed: bool
    validation_results: List[ValidationResult]
    completion_percentage: float
    key_concepts_mastered: List[str]
    issues_found: List[str]

class TutorialValidator:
    """Main validation class for the CAPTCHA handling tutorial"""
    
    def __init__(self):
        self.console = Console()
        self.tutorial_sections = {
            1: "Prerequisites and Environment Setup",
            2: "AgentCore Browser Tool Session Management",
            3: "Hybrid browser-use + AgentCore Integration",
            4: "AWS Bedrock AI Analysis Integration",
            5: "Production Workflows and Error Handling",
            6: "Complete Integration Examples and Best Practices"
        }
        self.validation_results = []
        
    def create_validation_result(self, section: str, check_name: str, 
                               passed: bool, message: str, 
                               details: Dict[str, Any] = None,
                               suggestions: List[str] = None) -> ValidationResult:
        """Create a validation result"""
        return ValidationResult(
            section=section,
            check_name=check_name,
            passed=passed,
            message=message,
            details=details or {},
            suggestions=suggestions or []
        )

    async def validate_environment_setup(self) -> List[ValidationResult]:
        """Validate Section 1: Prerequisites and Environment Setup"""
        results = []
        section = "Section 1: Prerequisites and Environment Setup"
        
        # Check Python version
        python_version = sys.version_info
        if python_version >= (3, 12):
            results.append(self.create_validation_result(
                section, "Python Version", True,
                f"✅ Python {python_version.major}.{python_version.minor} detected"
            ))
        else:
            results.append(self.create_validation_result(
                section, "Python Version", False,
                f"❌ Python {python_version.major}.{python_version.minor} found, requires 3.12+",
                suggestions=["Install Python 3.12 or higher", "Update your Python environment"]
            ))
        
        # Check required packages
        required_packages = [
            "boto3", "browser-use", "rich", "asyncio", "pathlib"
        ]
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
                results.append(self.create_validation_result(
                    section, f"Package: {package}", True,
                    f"✅ {package} is installed"
                ))
            except ImportError:
                results.append(self.create_validation_result(
                    section, f"Package: {package}", False,
                    f"❌ {package} is not installed",
                    suggestions=[f"Install {package} using: pip install {package}"]
                ))
        
        # Check AWS credentials
        try:
            import boto3
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                results.append(self.create_validation_result(
                    section, "AWS Credentials", True,
                    "✅ AWS credentials are configured"
                ))
            else:
                results.append(self.create_validation_result(
                    section, "AWS Credentials", False,
                    "❌ AWS credentials not found",
                    suggestions=[
                        "Configure AWS credentials using aws configure",
                        "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables",
                        "Use IAM roles if running on EC2"
                    ]
                ))
        except Exception as e:
            results.append(self.create_validation_result(
                section, "AWS Credentials", False,
                f"❌ Error checking AWS credentials: {str(e)}"
            ))
        
        return results

    async def validate_agentcore_integration(self) -> List[ValidationResult]:
        """Validate Section 2: AgentCore Browser Tool Session Management"""
        results = []
        section = "Section 2: AgentCore Browser Tool Session Management"
        
        # Check if AgentCore session management code exists
        session_files = [
            "agentcore_session_manager.py",
            "browser_session_handler.py"
        ]
        
        for file_name in session_files:
            file_path = Path(file_name)
            if file_path.exists():
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", True,
                    f"✅ {file_name} exists"
                ))
            else:
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", False,
                    f"❌ {file_name} not found",
                    suggestions=[f"Create {file_name} as shown in the tutorial"]
                ))
        
        return results

    async def validate_hybrid_integration(self) -> List[ValidationResult]:
        """Validate Section 3: Hybrid browser-use + AgentCore Integration"""
        results = []
        section = "Section 3: Hybrid browser-use + AgentCore Integration"
        
        # Check for hybrid integration files
        integration_files = [
            "hybrid_captcha_solver.py",
            "browser_agentcore_coordinator.py"
        ]
        
        for file_name in integration_files:
            file_path = Path(file_name)
            if file_path.exists():
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", True,
                    f"✅ {file_name} exists"
                ))
                
                # Check file content for key integration patterns
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        
                    key_patterns = [
                        "browser-use",
                        "AgentCore",
                        "async def",
                        "captcha"
                    ]
                    
                    for pattern in key_patterns:
                        if pattern in content:
                            results.append(self.create_validation_result(
                                section, f"Pattern: {pattern} in {file_name}", True,
                                f"✅ Found {pattern} integration pattern"
                            ))
                        else:
                            results.append(self.create_validation_result(
                                section, f"Pattern: {pattern} in {file_name}", False,
                                f"❌ Missing {pattern} integration pattern",
                                suggestions=[f"Add {pattern} integration as shown in tutorial"]
                            ))
                            
                except Exception as e:
                    results.append(self.create_validation_result(
                        section, f"Content Check: {file_name}", False,
                        f"❌ Error reading {file_name}: {str(e)}"
                    ))
            else:
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", False,
                    f"❌ {file_name} not found",
                    suggestions=[f"Create {file_name} as shown in the tutorial"]
                ))
        
        return results

    async def validate_bedrock_integration(self) -> List[ValidationResult]:
        """Validate Section 4: AWS Bedrock AI Analysis Integration"""
        results = []
        section = "Section 4: AWS Bedrock AI Analysis Integration"
        
        # Check Bedrock client initialization
        try:
            import boto3
            bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')
            results.append(self.create_validation_result(
                section, "Bedrock Client", True,
                "✅ Bedrock client can be initialized"
            ))
        except Exception as e:
            results.append(self.create_validation_result(
                section, "Bedrock Client", False,
                f"❌ Error initializing Bedrock client: {str(e)}",
                suggestions=[
                    "Check AWS credentials",
                    "Verify Bedrock service availability in your region",
                    "Ensure proper IAM permissions for Bedrock"
                ]
            ))
        
        # Check for AI analysis files
        ai_files = [
            "bedrock_captcha_analyzer.py",
            "ai_vision_processor.py"
        ]
        
        for file_name in ai_files:
            file_path = Path(file_name)
            if file_path.exists():
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", True,
                    f"✅ {file_name} exists"
                ))
            else:
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", False,
                    f"❌ {file_name} not found",
                    suggestions=[f"Create {file_name} as shown in the tutorial"]
                ))
        
        return results

    async def validate_production_workflows(self) -> List[ValidationResult]:
        """Validate Section 5: Production Workflows and Error Handling"""
        results = []
        section = "Section 5: Production Workflows and Error Handling"
        
        # Check for production-ready files
        production_files = [
            "error_handler.py",
            "monitoring_setup.py",
            "production_config.py"
        ]
        
        for file_name in production_files:
            file_path = Path(file_name)
            if file_path.exists():
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", True,
                    f"✅ {file_name} exists"
                ))
            else:
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", False,
                    f"❌ {file_name} not found",
                    suggestions=[f"Create {file_name} as shown in the tutorial"]
                ))
        
        return results

    async def validate_complete_integration(self) -> List[ValidationResult]:
        """Validate Section 6: Complete Integration Examples and Best Practices"""
        results = []
        section = "Section 6: Complete Integration Examples and Best Practices"
        
        # Check for complete integration examples
        example_files = [
            "complete_captcha_solution.py",
            "best_practices_demo.py",
            "integration_tests.py"
        ]
        
        for file_name in example_files:
            file_path = Path(file_name)
            if file_path.exists():
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", True,
                    f"✅ {file_name} exists"
                ))
            else:
                results.append(self.create_validation_result(
                    section, f"File: {file_name}", False,
                    f"❌ {file_name} not found",
                    suggestions=[f"Create {file_name} as shown in the tutorial"]
                ))
        
        return results

    def display_validation_results(self, results: List[ValidationResult]):
        """Display validation results in a beautiful format"""
        
        # Group results by section
        sections = {}
        for result in results:
            if result.section not in sections:
                sections[result.section] = []
            sections[result.section].append(result)
        
        # Display each section
        for section_name, section_results in sections.items():
            
            # Calculate section statistics
            total_checks = len(section_results)
            passed_checks = sum(1 for r in section_results if r.passed)
            completion_percentage = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
            
            # Create section panel
            status_color = "green" if completion_percentage == 100 else "yellow" if completion_percentage >= 50 else "red"
            
            panel_content = f"[bold]{section_name}[/bold]\n"
            panel_content += f"Progress: {passed_checks}/{total_checks} checks passed ({completion_percentage:.1f}%)\n\n"
            
            # Add individual check results
            for result in section_results:
                status_icon = "✅" if result.passed else "❌"
                panel_content += f"{status_icon} {result.check_name}: {result.message}\n"
                
                if result.suggestions:
                    panel_content += "   💡 Suggestions:\n"
                    for suggestion in result.suggestions:
                        panel_content += f"      • {suggestion}\n"
                    panel_content += "\n"
            
            self.console.print(Panel(
                panel_content.strip(),
                title=f"[bold {status_color}]{section_name}[/bold {status_color}]",
                border_style=status_color
            ))
            self.console.print()

    async def run_full_validation(self):
        """Run complete validation for all tutorial sections"""
        
        self.console.print(Panel(
            "[bold blue]🧪 CAPTCHA Handling Tutorial - Complete Validation[/bold blue]\n\n"
            "Running comprehensive validation across all tutorial sections...",
            title="[bold blue]Validation Started[/bold blue]",
            border_style="blue"
        ))
        
        all_results = []
        
        # Run all validation sections
        validation_functions = [
            self.validate_environment_setup,
            self.validate_agentcore_integration,
            self.validate_hybrid_integration,
            self.validate_bedrock_integration,
            self.validate_production_workflows,
            self.validate_complete_integration
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            
            for i, validation_func in enumerate(validation_functions, 1):
                task = progress.add_task(f"Validating Section {i}...", total=None)
                
                try:
                    results = await validation_func()
                    all_results.extend(results)
                    progress.update(task, description=f"✅ Section {i} validated")
                except Exception as e:
                    self.console.print(f"[red]❌ Error validating section {i}: {str(e)}[/red]")
                    progress.update(task, description=f"❌ Section {i} failed")
                
                progress.remove_task(task)
        
        # Display results
        self.display_validation_results(all_results)
        
        # Generate summary
        total_checks = len(all_results)
        passed_checks = sum(1 for r in all_results if r.passed)
        overall_percentage = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
        
        summary_color = "green" if overall_percentage == 100 else "yellow" if overall_percentage >= 70 else "red"
        
        self.console.print(Panel(
            f"[bold]Overall Tutorial Completion: {passed_checks}/{total_checks} ({overall_percentage:.1f}%)[/bold]\n\n"
            f"{'🎉 Congratulations! Tutorial completed successfully!' if overall_percentage == 100 else '📚 Continue working through the tutorial sections above.'}\n\n"
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            title=f"[bold {summary_color}]Validation Summary[/bold {summary_color}]",
            border_style=summary_color
        ))

# Initialize the validator
validator = TutorialValidator()
console.print("[bold green]✅ Validation Framework Ready[/bold green]")

# Main execution
if __name__ == "__main__":
    # Run the validation
    asyncio.run(validator.run_full_validation())