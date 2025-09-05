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

    @abstractmethod
    def get_service_type(self) -> str:
        """Get the service type identifier"""
        pass


class OllamaLLMService(BaseLLMService):
    """Ollama LLM service implementation"""

    def __init__(self, model_name: str = "deepseek-r1:14b", base_url: str = "http://localhost:11434"):
        if base_url is None:
            base_url = "http://localhost:11434"
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

    def get_service_type(self) -> str:
        """Get the service type identifier"""
        return "ollama"


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

    def get_service_type(self) -> str:
        """Get the service type identifier"""
        return "openai"


class GoogleGeminiLLMService(BaseLLMService):
    """Google Gemini LLM service implementation"""

    def __init__(self, model_name: str = "gemini-1.5-flash", api_key: str = None):
        super().__init__(model_name, "https://generativelanguage.googleapis.com/v1beta", api_key)
        self.endpoint = f"{self.base_url}/models/{self.model_name}:generateContent"

    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using Google Gemini API"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=kwargs.get('temperature', 0.7),
                    top_p=kwargs.get('top_p', 0.8),
                    top_k=kwargs.get('top_k', 40),
                    max_output_tokens=kwargs.get('max_output_tokens', 8192),
                )
            )

            return {
                "success": True,
                "response": response.text,
                "model": self.model_name,
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(response.text.split()) if response.text else 0
                },
                "finish_reason": "stop"
            }

        except ImportError:
            self.logger.error("google-generativeai package not installed")
            return {
                "success": False,
                "error": "Google Generative AI package not installed",
                "response": ""
            }
        except Exception as e:
            self.logger.error(f"Google Gemini API request failed: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}",
                "response": ""
            }

    def is_available(self) -> bool:
        """Check if Google Gemini service is available"""
        if not self.api_key:
            return False

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            models = genai.list_models()
            return True
        except ImportError:
            return False
        except Exception:
            return False

    def get_service_type(self) -> str:
        """Get the service type identifier"""
        return "gemini"


class ClaudeLLMService(BaseLLMService):
    """Anthropic Claude LLM service implementation"""

    def __init__(self, model_name: str = "claude-3-sonnet-20240229", api_key: str = None):
        super().__init__(model_name, "https://api.anthropic.com", api_key)
        self.endpoint = f"{self.base_url}/v1/messages"

    def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate response using Claude API"""
        try:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }

            payload = {
                "model": self.model_name,
                "max_tokens": kwargs.get('max_tokens', 4096),
                "messages": [{"role": "user", "content": prompt}],
                **{k: v for k, v in kwargs.items() if k != 'max_tokens'}
            }

            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            content = result.get("content", [{}])[0].get("text", "")

            return {
                "success": True,
                "response": content,
                "model": self.model_name,
                "usage": result.get("usage", {}),
                "stop_reason": result.get("stop_reason", "")
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Claude API request failed: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}",
                "response": ""
            }
        except Exception as e:
            self.logger.error(f"Unexpected error in Claude service: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "response": ""
            }

    def is_available(self) -> bool:
        """Check if Claude service is available"""
        return bool(self.api_key)

    def get_service_type(self) -> str:
        """Get the service type identifier"""
        return "claude"


class LLMFactory:
    """Factory for creating LLM service instances using OOP principles"""

    _services = {
        "ollama": OllamaLLMService,
        "openai": OpenAILLMService,
        "gemini": GoogleGeminiLLMService,
        "claude": ClaudeLLMService
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

        # Check Google Gemini (requires API key)
        try:
            gemini_service = cls.create_service("gemini", api_key="dummy")
            availability["gemini"] = gemini_service.is_available()
        except Exception as e:
            logger.warning(f"Could not check Google Gemini availability: {e}")
            availability["gemini"] = False

        # Check Claude (requires API key)
        try:
            claude_service = cls.create_service("claude", api_key="dummy")
            availability["claude"] = claude_service.is_available()
        except Exception as e:
            logger.warning(f"Could not check Claude availability: {e}")
            availability["claude"] = False

        return availability

    @classmethod
    def get_default_service(cls) -> BaseLLMService:
        """Get the default LLM service (Ollama if available)"""
        availability = cls.get_available_services()

        if availability.get("ollama", False):
            return cls.create_service("ollama", model_name="deepseek-r1:14b")
        elif availability.get("openai", False):
            return cls.create_service("openai")
        elif availability.get("claude", False):
            return cls.create_service("claude")
        else:
            return cls.create_service("ollama", model_name="deepseek-r1:14b")

    @classmethod
    def get_supported_services(cls) -> list[str]:
        """Get list of all supported service types"""
        return list(cls._services.keys())
