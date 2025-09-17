"""
Bedrock vision model integration for AgentCore browser tool screenshots.

This module provides multi-modal AI capabilities for analyzing CAPTCHA images
captured by AgentCore browser tool, including image preprocessing, prompt
templates, and confidence scoring mechanisms.
"""

import asyncio
import base64
import io
import json
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from PIL import Image, ImageEnhance, ImageFilter
import boto3
from botocore.exceptions import ClientError

from config import ConfigurationManager
from exceptions import AgentCoreBrowserError, BrowserErrorType


logger = logging.getLogger(__name__)


class CaptchaType(Enum):
    """Types of CAPTCHAs that can be detected and solved."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    FUNCAPTCHA = "funcaptcha"
    CLOUDFLARE = "cloudflare"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence levels for CAPTCHA solutions."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class CaptchaAnalysisResult:
    """Result of CAPTCHA analysis using vision models."""
    captcha_detected: bool
    captcha_type: CaptchaType
    confidence_score: float
    solution: Optional[str] = None
    solution_confidence: Optional[float] = None
    challenge_text: Optional[str] = None
    visual_elements: Optional[List[Dict[str, Any]]] = None
    processing_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ImagePreprocessingConfig:
    """Configuration for image preprocessing pipeline."""
    resize_width: Optional[int] = None
    resize_height: Optional[int] = None
    enhance_contrast: bool = True
    enhance_sharpness: bool = True
    enhance_brightness: bool = False
    apply_noise_reduction: bool = True
    convert_to_grayscale: bool = False
    normalize_colors: bool = True
    crop_padding: int = 10


class BedrockVisionClient:
    """Client for interacting with Bedrock vision models for CAPTCHA analysis."""
    
    def __init__(self, config_manager: Optional[ConfigurationManager] = None):
        """
        Initialize Bedrock vision client.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigurationManager()
        self._bedrock_client = None
        self._model_config = None
        self._preprocessing_config = ImagePreprocessingConfig()
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load Bedrock and model configuration."""
        try:
            aws_credentials = self.config_manager.get_aws_credentials()
            region = aws_credentials.get('region', 'us-east-1')
            
            # Initialize Bedrock client
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=region,
                aws_access_key_id=aws_credentials.get('aws_access_key_id'),
                aws_secret_access_key=aws_credentials.get('aws_secret_access_key'),
                aws_session_token=aws_credentials.get('aws_session_token')
            )
            
            # Load model configuration
            integration_config = self.config_manager.get_integration_config()
            self._model_config = {
                'vision_model': getattr(integration_config, 'vision_model', 'anthropic.claude-3-sonnet-20240229-v1:0'),
                'max_tokens': getattr(integration_config, 'max_tokens', 4096),
                'temperature': getattr(integration_config, 'temperature', 0.1),
                'top_p': getattr(integration_config, 'top_p', 0.9)
            }
            
            logger.info(f"Initialized Bedrock vision client with model: {self._model_config['vision_model']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock vision client: {e}")
            raise AgentCoreBrowserError(
                f"Failed to initialize vision model client: {str(e)}",
                error_type=BrowserErrorType.CONFIGURATION_ERROR,
                recoverable=False
            )
    
    def set_preprocessing_config(self, config: ImagePreprocessingConfig):
        """
        Set image preprocessing configuration.
        
        Args:
            config: Preprocessing configuration
        """
        self._preprocessing_config = config
        logger.info("Updated image preprocessing configuration")
    
    def preprocess_image(self, image_data: bytes) -> bytes:
        """
        Preprocess CAPTCHA image for better analysis.
        
        Args:
            image_data: Raw image bytes from AgentCore browser tool
            
        Returns:
            Preprocessed image bytes
        """
        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Apply preprocessing steps
            config = self._preprocessing_config
            
            # Resize if specified
            if config.resize_width and config.resize_height:
                image = image.resize((config.resize_width, config.resize_height), Image.Resampling.LANCZOS)
            
            # Enhance contrast
            if config.enhance_contrast:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            if config.enhance_sharpness:
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(1.1)
            
            # Enhance brightness
            if config.enhance_brightness:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(1.1)
            
            # Apply noise reduction
            if config.apply_noise_reduction:
                image = image.filter(ImageFilter.MedianFilter(size=3))
            
            # Convert to grayscale if specified
            if config.convert_to_grayscale:
                image = image.convert('L').convert('RGB')
            
            # Normalize colors
            if config.normalize_colors:
                # Simple normalization by adjusting levels
                enhancer = ImageEnhance.Color(image)
                image = enhancer.enhance(1.1)
            
            # Convert back to bytes
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='PNG', optimize=True)
            preprocessed_data = output_buffer.getvalue()
            
            logger.debug(f"Preprocessed image: {len(image_data)} -> {len(preprocessed_data)} bytes")
            return preprocessed_data
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed, using original: {e}")
            return image_data
    
    def _get_captcha_analysis_prompt(self, captcha_type: Optional[CaptchaType] = None) -> str:
        """
        Get prompt template for CAPTCHA analysis.
        
        Args:
            captcha_type: Specific CAPTCHA type to analyze
            
        Returns:
            Formatted prompt string
        """
        base_prompt = """
You are an expert at analyzing CAPTCHA challenges. Please analyze the provided image and:

1. Determine if this is a CAPTCHA challenge
2. Identify the type of CAPTCHA (text, image selection, reCAPTCHA, hCaptcha, etc.)
3. Extract any text or instructions visible in the image
4. If it's a solvable CAPTCHA, provide the solution
5. Rate your confidence in the solution (0.0 to 1.0)

Please respond in JSON format with the following structure:
{
    "captcha_detected": boolean,
    "captcha_type": "text|image|recaptcha_v2|recaptcha_v3|hcaptcha|funcaptcha|cloudflare|custom|unknown",
    "confidence_score": float (0.0 to 1.0),
    "challenge_text": "string describing the challenge",
    "solution": "string with the solution if solvable",
    "solution_confidence": float (0.0 to 1.0),
    "visual_elements": [
        {
            "type": "string describing element type",
            "description": "string describing what you see",
            "location": "string describing location in image"
        }
    ],
    "reasoning": "string explaining your analysis"
}
"""
        
        if captcha_type == CaptchaType.TEXT:
            return base_prompt + """
Focus specifically on text-based CAPTCHAs. Look for:
- Distorted text that needs to be read
- Numbers or letters in various fonts
- Text with noise, lines, or other obfuscation
- Case sensitivity requirements
"""
        
        elif captcha_type == CaptchaType.IMAGE:
            return base_prompt + """
Focus specifically on image-based CAPTCHAs. Look for:
- Grid of images to select from
- Instructions like "Select all images with cars"
- Traffic lights, crosswalks, vehicles, storefronts
- Multiple choice image selection challenges
"""
        
        elif captcha_type == CaptchaType.RECAPTCHA_V2:
            return base_prompt + """
Focus specifically on reCAPTCHA v2 challenges. Look for:
- "I'm not a robot" checkbox
- Image grid selection challenges
- Google reCAPTCHA branding
- "Select all images with..." instructions
"""
        
        elif captcha_type == CaptchaType.HCAPTCHA:
            return base_prompt + """
Focus specifically on hCaptcha challenges. Look for:
- hCaptcha branding or logo
- Image selection grids
- Accessibility options
- "Please click each image containing..." instructions
"""
        
        return base_prompt
    
    def _get_text_captcha_prompt(self) -> str:
        """Get specialized prompt for text-based CAPTCHA solving."""
        return """
You are analyzing a text-based CAPTCHA image. Please:

1. Carefully read any distorted or obfuscated text in the image
2. Account for common CAPTCHA techniques like:
   - Rotated or skewed characters
   - Overlapping lines or noise
   - Unusual fonts or character spacing
   - Mixed case letters and numbers
3. Provide the exact text as it appears, maintaining case sensitivity
4. If uncertain about specific characters, indicate alternatives

Respond in JSON format:
{
    "text_detected": "exact text you can read",
    "confidence": float (0.0 to 1.0),
    "uncertain_characters": [
        {
            "position": int,
            "character": "best guess",
            "alternatives": ["other possible characters"]
        }
    ],
    "case_sensitive": boolean,
    "character_count": int,
    "contains_numbers": boolean,
    "contains_letters": boolean,
    "contains_symbols": boolean
}
"""
    
    def _get_image_captcha_prompt(self) -> str:
        """Get specialized prompt for image-based CAPTCHA solving."""
        return """
You are analyzing an image-based CAPTCHA challenge. Please:

1. Identify the instruction text (e.g., "Select all images with traffic lights")
2. Analyze each image in the grid
3. Determine which images match the criteria
4. Consider common CAPTCHA image categories:
   - Vehicles (cars, buses, motorcycles, bicycles)
   - Traffic elements (traffic lights, crosswalks, street signs)
   - Buildings (storefronts, houses, bridges)
   - Nature (trees, mountains, water)

Respond in JSON format:
{
    "instruction": "the challenge instruction text",
    "grid_size": "description of grid layout (e.g., 3x3, 4x4)",
    "images_to_select": [
        {
            "position": "grid position (e.g., top-left, center, etc.)",
            "row": int,
            "column": int,
            "matches_criteria": boolean,
            "description": "what you see in this image",
            "confidence": float (0.0 to 1.0)
        }
    ],
    "overall_confidence": float (0.0 to 1.0)
}
"""
    
    async def analyze_captcha(self, 
                            image_data: bytes,
                            captcha_type: Optional[CaptchaType] = None,
                            preprocess: bool = True) -> CaptchaAnalysisResult:
        """
        Analyze CAPTCHA image using Bedrock vision model.
        
        Args:
            image_data: Screenshot data from AgentCore browser tool
            captcha_type: Specific CAPTCHA type hint for analysis
            preprocess: Whether to preprocess the image
            
        Returns:
            CaptchaAnalysisResult with analysis results
        """
        start_time = datetime.now()
        
        try:
            # Preprocess image if requested
            if preprocess:
                processed_image = self.preprocess_image(image_data)
            else:
                processed_image = image_data
            
            # Encode image for Bedrock
            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            
            # Get appropriate prompt
            prompt = self._get_captcha_analysis_prompt(captcha_type)
            
            # Prepare Bedrock request
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self._model_config['max_tokens'],
                "temperature": self._model_config['temperature'],
                "top_p": self._model_config['top_p'],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            # Call Bedrock
            response = self._bedrock_client.invoke_model(
                modelId=self._model_config['vision_model'],
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract JSON from response
            analysis_data = self._extract_json_from_response(content)
            
            # Calculate processing time
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Create result object
            result = CaptchaAnalysisResult(
                captcha_detected=analysis_data.get('captcha_detected', False),
                captcha_type=CaptchaType(analysis_data.get('captcha_type', 'unknown')),
                confidence_score=analysis_data.get('confidence_score', 0.0),
                solution=analysis_data.get('solution'),
                solution_confidence=analysis_data.get('solution_confidence'),
                challenge_text=analysis_data.get('challenge_text'),
                visual_elements=analysis_data.get('visual_elements', []),
                processing_time_ms=processing_time,
                model_used=self._model_config['vision_model']
            )
            
            logger.info(f"CAPTCHA analysis completed in {processing_time}ms: "
                       f"detected={result.captcha_detected}, type={result.captcha_type}, "
                       f"confidence={result.confidence_score}")
            
            return result
            
        except ClientError as e:
            error_msg = f"Bedrock API error: {str(e)}"
            logger.error(error_msg)
            return CaptchaAnalysisResult(
                captcha_detected=False,
                captcha_type=CaptchaType.UNKNOWN,
                confidence_score=0.0,
                error_message=error_msg,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        
        except Exception as e:
            error_msg = f"CAPTCHA analysis failed: {str(e)}"
            logger.error(error_msg)
            return CaptchaAnalysisResult(
                captcha_detected=False,
                captcha_type=CaptchaType.UNKNOWN,
                confidence_score=0.0,
                error_message=error_msg,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def solve_text_captcha(self, image_data: bytes) -> CaptchaAnalysisResult:
        """
        Specialized method for solving text-based CAPTCHAs.
        
        Args:
            image_data: Screenshot data from AgentCore browser tool
            
        Returns:
            CaptchaAnalysisResult with text solution
        """
        start_time = datetime.now()
        
        try:
            # Preprocess image with text-optimized settings
            text_config = ImagePreprocessingConfig(
                enhance_contrast=True,
                enhance_sharpness=True,
                apply_noise_reduction=True,
                convert_to_grayscale=True,
                normalize_colors=False
            )
            
            original_config = self._preprocessing_config
            self._preprocessing_config = text_config
            
            processed_image = self.preprocess_image(image_data)
            
            # Restore original config
            self._preprocessing_config = original_config
            
            # Encode image
            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            
            # Use specialized text prompt
            prompt = self._get_text_captcha_prompt()
            
            # Prepare Bedrock request
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.0,  # Lower temperature for text accuracy
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            # Call Bedrock
            response = self._bedrock_client.invoke_model(
                modelId=self._model_config['vision_model'],
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract JSON from response
            text_data = self._extract_json_from_response(content)
            
            # Calculate processing time
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Create result object
            result = CaptchaAnalysisResult(
                captcha_detected=True,
                captcha_type=CaptchaType.TEXT,
                confidence_score=text_data.get('confidence', 0.0),
                solution=text_data.get('text_detected'),
                solution_confidence=text_data.get('confidence', 0.0),
                challenge_text="Text-based CAPTCHA",
                processing_time_ms=processing_time,
                model_used=self._model_config['vision_model']
            )
            
            logger.info(f"Text CAPTCHA solved in {processing_time}ms: "
                       f"solution='{result.solution}', confidence={result.confidence_score}")
            
            return result
            
        except Exception as e:
            error_msg = f"Text CAPTCHA solving failed: {str(e)}"
            logger.error(error_msg)
            return CaptchaAnalysisResult(
                captcha_detected=True,
                captcha_type=CaptchaType.TEXT,
                confidence_score=0.0,
                error_message=error_msg,
                processing_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON data from model response text.
        
        Args:
            response_text: Raw response text from vision model
            
        Returns:
            Parsed JSON data dictionary
        """
        try:
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            
            # If no JSON found, return empty dict
            logger.warning("No JSON found in vision model response")
            return {}
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from vision model response: {e}")
            return {}
    
    def calculate_confidence_level(self, confidence_score: float) -> ConfidenceLevel:
        """
        Convert numeric confidence score to confidence level.
        
        Args:
            confidence_score: Numeric confidence (0.0 to 1.0)
            
        Returns:
            ConfidenceLevel enum value
        """
        if confidence_score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def validate_solution(self, 
                         solution: str, 
                         captcha_type: CaptchaType,
                         confidence_threshold: float = 0.7) -> Tuple[bool, str]:
        """
        Validate CAPTCHA solution based on type and confidence.
        
        Args:
            solution: Proposed solution
            captcha_type: Type of CAPTCHA
            confidence_threshold: Minimum confidence required
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        if not solution:
            return False, "No solution provided"
        
        if captcha_type == CaptchaType.TEXT:
            # Validate text CAPTCHA solution
            if len(solution.strip()) == 0:
                return False, "Empty text solution"
            
            # Check for reasonable length (most text CAPTCHAs are 4-8 characters)
            if len(solution) < 2 or len(solution) > 20:
                return False, f"Unusual text length: {len(solution)} characters"
            
            # Check for valid characters (alphanumeric is most common)
            if not solution.replace(' ', '').isalnum():
                return False, "Solution contains invalid characters"
            
            return True, "Text solution appears valid"
        
        elif captcha_type == CaptchaType.IMAGE:
            # For image CAPTCHAs, solution might be grid positions
            return True, "Image solution validation not implemented"
        
        else:
            return True, f"Validation not implemented for {captcha_type}"


class CaptchaSolutionValidator:
    """Validates CAPTCHA solutions using AgentCore browser tool feedback."""
    
    def __init__(self, browser_client):
        """
        Initialize solution validator.
        
        Args:
            browser_client: AgentCore browser client for feedback
        """
        self.browser_client = browser_client
        self.solution_history: List[Dict[str, Any]] = []
    
    async def validate_solution_with_feedback(self, 
                                            solution: str,
                                            captcha_type: CaptchaType,
                                            submit_element_selector: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate CAPTCHA solution by submitting it and checking AgentCore feedback.
        
        Args:
            solution: CAPTCHA solution to validate
            captcha_type: Type of CAPTCHA being solved
            submit_element_selector: Selector for submit button/element
            
        Returns:
            Validation result dictionary
        """
        validation_start = datetime.now()
        
        try:
            # Record attempt
            attempt_record = {
                "solution": solution,
                "captcha_type": captcha_type.value,
                "timestamp": validation_start.isoformat(),
                "success": False,
                "error_message": None,
                "response_time_ms": None
            }
            
            # Submit solution based on CAPTCHA type
            if captcha_type == CaptchaType.TEXT:
                # For text CAPTCHAs, find input field and submit
                result = await self._submit_text_solution(solution, submit_element_selector)
            elif captcha_type == CaptchaType.IMAGE:
                # For image CAPTCHAs, handle grid selection
                result = await self._submit_image_solution(solution, submit_element_selector)
            else:
                result = {
                    "success": False,
                    "error": f"Solution validation not implemented for {captcha_type}"
                }
            
            # Calculate response time
            response_time = int((datetime.now() - validation_start).total_seconds() * 1000)
            
            # Update attempt record
            attempt_record.update({
                "success": result.get("success", False),
                "error_message": result.get("error"),
                "response_time_ms": response_time
            })
            
            # Store in history
            self.solution_history.append(attempt_record)
            
            # Return validation result
            return {
                "valid": result.get("success", False),
                "feedback": result.get("feedback", "No feedback available"),
                "error": result.get("error"),
                "response_time_ms": response_time,
                "attempt_number": len(self.solution_history)
            }
            
        except Exception as e:
            error_msg = f"Solution validation failed: {str(e)}"
            logger.error(error_msg)
            
            # Record failed attempt
            attempt_record.update({
                "success": False,
                "error_message": error_msg,
                "response_time_ms": int((datetime.now() - validation_start).total_seconds() * 1000)
            })
            self.solution_history.append(attempt_record)
            
            return {
                "valid": False,
                "feedback": "Validation error occurred",
                "error": error_msg,
                "response_time_ms": attempt_record["response_time_ms"],
                "attempt_number": len(self.solution_history)
            }
    
    async def _submit_text_solution(self, 
                                   solution: str, 
                                   submit_element_selector: Optional[str] = None) -> Dict[str, Any]:
        """Submit text-based CAPTCHA solution."""
        try:
            # Find CAPTCHA input field (common selectors)
            input_selectors = [
                "input[type='text'][name*='captcha']",
                "input[type='text'][id*='captcha']",
                "input[type='text'][class*='captcha']",
                ".captcha-input",
                "#captcha-input",
                "input[placeholder*='captcha']"
            ]
            
            input_found = False
            for selector in input_selectors:
                try:
                    from interfaces import ElementSelector
                    element_selector = ElementSelector(css_selector=selector)
                    
                    # Type solution into input field
                    response = await self.browser_client.type_text(
                        element_selector=element_selector,
                        text=solution,
                        clear_first=True
                    )
                    
                    if response.success:
                        input_found = True
                        break
                        
                except Exception:
                    continue
            
            if not input_found:
                return {"success": False, "error": "Could not find CAPTCHA input field"}
            
            # Submit the form
            if submit_element_selector:
                from interfaces import ElementSelector
                submit_selector = ElementSelector(css_selector=submit_element_selector)
                submit_response = await self.browser_client.click_element(submit_selector)
                
                if not submit_response.success:
                    return {"success": False, "error": "Failed to click submit button"}
            
            # Wait a moment for response
            await asyncio.sleep(2)
            
            # Check for success/failure indicators
            success_indicators = [
                "success", "correct", "verified", "passed"
            ]
            
            error_indicators = [
                "incorrect", "wrong", "invalid", "failed", "error"
            ]
            
            # Extract page text to check for indicators
            page_response = await self.browser_client.extract_text()
            if page_response.success:
                page_text = page_response.data.get("text", "").lower()
                
                # Check for success indicators
                for indicator in success_indicators:
                    if indicator in page_text:
                        return {
                            "success": True,
                            "feedback": f"Success indicator found: {indicator}"
                        }
                
                # Check for error indicators
                for indicator in error_indicators:
                    if indicator in page_text:
                        return {
                            "success": False,
                            "feedback": f"Error indicator found: {indicator}"
                        }
            
            # If no clear indicators, assume success if no errors
            return {
                "success": True,
                "feedback": "Solution submitted, no clear success/failure indicators"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _submit_image_solution(self, 
                                    solution: str, 
                                    submit_element_selector: Optional[str] = None) -> Dict[str, Any]:
        """Submit image-based CAPTCHA solution."""
        # This would implement image grid selection logic
        # For now, return not implemented
        return {
            "success": False,
            "error": "Image CAPTCHA solution submission not yet implemented"
        }
    
    def get_solution_statistics(self) -> Dict[str, Any]:
        """Get statistics about solution attempts."""
        if not self.solution_history:
            return {"total_attempts": 0}
        
        total_attempts = len(self.solution_history)
        successful_attempts = sum(1 for attempt in self.solution_history if attempt["success"])
        
        # Calculate average response time
        response_times = [
            attempt["response_time_ms"] 
            for attempt in self.solution_history 
            if attempt["response_time_ms"] is not None
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Group by CAPTCHA type
        type_stats = {}
        for attempt in self.solution_history:
            captcha_type = attempt["captcha_type"]
            if captcha_type not in type_stats:
                type_stats[captcha_type] = {"total": 0, "successful": 0}
            
            type_stats[captcha_type]["total"] += 1
            if attempt["success"]:
                type_stats[captcha_type]["successful"] += 1
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0,
            "average_response_time_ms": avg_response_time,
            "type_statistics": type_stats,
            "recent_attempts": self.solution_history[-5:]  # Last 5 attempts
        }