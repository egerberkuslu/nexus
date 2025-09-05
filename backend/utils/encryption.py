"""
Encryption utilities for secure storage of sensitive data like API keys
"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class EncryptionManager:
    """Manages encryption and decryption of sensitive data"""
    
    def __init__(self, password: Optional[str] = None):
        """
        Initialize encryption manager
        
        Args:
            password: Password for encryption. If None, will use environment variable or generate one
        """
        self.password = password or os.getenv('ENCRYPTION_PASSWORD')
        if not self.password:
            # Generate a default password if none provided
            self.password = self._generate_default_password()
            logger.warning("No encryption password provided. Using generated password. Store this securely!")
            logger.info(f"Generated password: {self.password}")
        
        self._fernet = None
        self._initialize_fernet()
    
    def _generate_default_password(self) -> str:
        """Generate a default password for encryption"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
    
    def _initialize_fernet(self):
        """Initialize Fernet cipher with password-derived key"""
        try:
            # Derive key from password
            password_bytes = self.password.encode('utf-8')
            salt = b'mininet_web_framework_salt'  # Fixed salt for consistency
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
            self._fernet = Fernet(key)
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt a string
        
        Args:
            data: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        try:
            if not self._fernet:
                raise ValueError("Encryption not initialized")
            
            encrypted_data = self._fernet.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encrypt data: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt a string
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted string
        """
        try:
            if not self._fernet:
                raise ValueError("Encryption not initialized")
            
            # Decode base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # Decrypt
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise
    
    def is_encrypted(self, data: str) -> bool:
        """
        Check if a string appears to be encrypted
        
        Args:
            data: String to check
            
        Returns:
            True if data appears to be encrypted
        """
        try:
            # Try to decode as base64
            base64.urlsafe_b64decode(data.encode('utf-8'))
            return True
        except Exception:
            return False


# Global encryption manager instance
_encryption_manager = None


def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key
    
    Args:
        api_key: API key to encrypt
        
    Returns:
        Encrypted API key
    """
    return get_encryption_manager().encrypt(api_key)


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt an API key
    
    Args:
        encrypted_api_key: Encrypted API key
        
    Returns:
        Decrypted API key
    """
    return get_encryption_manager().decrypt(encrypted_api_key)


def is_api_key_encrypted(api_key: str) -> bool:
    """
    Check if an API key is encrypted
    
    Args:
        api_key: API key to check
        
    Returns:
        True if API key appears to be encrypted
    """
    return get_encryption_manager().is_encrypted(api_key)
