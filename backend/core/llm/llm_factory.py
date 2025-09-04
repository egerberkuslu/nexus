"""
LLM Factory
Factory pattern for creating different LLM service instances
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests
import json

from utils.logger import setup_logger

logger = setup_logger(__name__)


class BaseLLMService(ABC):
    """Abstract base class for LLM services"""
    
    def __init__(self, model_name: str, base_url: str = None, api_key: str = None):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.logger = logger
    
    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate a response from the LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is available"""
        pass


class OllamaLLMService(BaseLLMService):
    """Ollama LLM service implementation"""
    
    def __init__(self, model_name: str = "deepseek-r1:14b", base_url: str = "http://localhost:11434"):
        super().__init__(model_name, base_url)
        self.endpoint = f"{self.base_url}/api/generate"
    
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using Ollama API"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                **kwargs
            }
            
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=240
            )
            response.raise_for_status()
            
            result = response.json()
            
            return {
                "success": True,
                "response": result.get("response", ""),
                "model": self.model_name,
                "done": result.get("done", False),
                "total_duration": result.get("total_duration", 0),
                "load_duration": result.get("load_duration", 0),
                "prompt_eval_duration": result.get("prompt_eval_duration", 0),
                "eval_duration": result.get("eval_duration", 0)
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ollama API request failed: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}",
                "response": ""
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in Ollama service: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "response": ""
            }
    
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


class OpenAILLMService(BaseLLMService):
    """OpenAI LLM service implementation"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", api_key: str = None):
        super().__init__(model_name, "https://api.openai.com/v1", api_key)
        self.endpoint = f"{self.base_url}/chat/completions"
    
    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                **kwargs
            }
            
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            message = result.get("choices", [{}])[0].get("message", {})
            
            return {
                "success": True,
                "response": message.get("content", ""),
                "model": self.model_name,
                "usage": result.get("usage", {}),
                "finish_reason": result.get("choices", [{}])[0].get("finish_reason", "")
            }
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"OpenAI API request failed: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}",
                "response": ""
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in OpenAI service: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "response": ""
            }
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available"""
        return bool(self.api_key)


class LLMFactory:
    """Factory for creating LLM service instances"""
    
    _services = {
        "ollama": OllamaLLMService,
        "openai": OpenAILLMService
    }
    
    @classmethod
    def create_service(cls, service_type: str, **kwargs) -> BaseLLMService:
        """Create an LLM service instance"""
        if service_type not in cls._services:
            raise ValueError(f"Unknown LLM service type: {service_type}")
        
        service_class = cls._services[service_type]
        return service_class(**kwargs)
    
    @classmethod
    def get_available_services(cls) -> Dict[str, bool]:
        """Check which services are available"""
        availability = {}
        
        # Check Ollama
        try:
            ollama_service = cls.create_service("ollama")
            availability["ollama"] = ollama_service.is_available()
        except Exception as e:
            logger.warning(f"Could not check Ollama availability: {e}")
            availability["ollama"] = False
        
        # Check OpenAI (requires API key)
        try:
            openai_service = cls.create_service("openai", api_key="dummy")
            availability["openai"] = openai_service.is_available()
        except Exception as e:
            logger.warning(f"Could not check OpenAI availability: {e}")
            availability["openai"] = False
        
        return availability
    
    @classmethod
    def get_default_service(cls) -> BaseLLMService:
        """Get the default LLM service (Ollama if available)"""
        availability = cls.get_available_services()
        
        if availability.get("ollama", False):
            return cls.create_service("ollama", model_name="deepseek-r1:14b")
        elif availability.get("openai", False):
            return cls.create_service("openai")
        else:
            # Fallback to Ollama even if not available
            return cls.create_service("ollama", model_name="deepseek-r1:14b")
