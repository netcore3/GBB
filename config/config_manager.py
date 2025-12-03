"""Configuration manager for BBS P2P Application.

This module handles loading, validating, and persisting application configuration.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class NetworkConfig:
    """Network configuration settings."""
    listen_port: int = 9000
    enable_mdns: bool = True
    enable_dht: bool = False
    bootstrap_nodes: list = field(default_factory=lambda: [
        "bootstrap1.bbs-p2p.example.com:8468",
        "bootstrap2.bbs-p2p.example.com:8468"
    ])
    max_peers: int = 100
    connection_timeout: int = 30


@dataclass
class UIConfig:
    """UI configuration settings."""
    theme: str = "dark"
    enable_acrylic: bool = True
    font_size: int = 12
    language: str = "en"
    avatar_name: str = ""


@dataclass
class SecurityConfig:
    """Security configuration settings."""
    key_store_path: str = "~/.bbs_p2p/keys/keystore.enc"
    encryption_algorithm: str = "chacha20poly1305"
    require_signature_verification: bool = True


@dataclass
class StorageConfig:
    """Storage configuration settings."""
    db_path: str = "~/.bbs_p2p/data/bbs.db"
    shared_folder: str = "~/.bbs_p2p/shared"
    max_attachment_size: int = 52428800  # 50 MB
    cache_size: int = 1073741824  # 1 GB


@dataclass
class SyncConfig:
    """Synchronization configuration settings."""
    interval: int = 30
    batch_size: int = 50
    max_retries: int = 3


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    log_path: str = "~/.bbs_p2p/logs/app.log"
    max_log_size: int = 10485760  # 10 MB
    backup_count: int = 5


class ConfigManager:
    """Manages application configuration with validation and persistence."""
    
    DEFAULT_CONFIG_PATH = Path.home() / ".bbs_p2p" / "config" / "settings.yaml"
    BUNDLED_CONFIG_PATH = Path(__file__).parent / "settings.yaml"
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Optional custom path to configuration file.
                        If None, uses default user config path.
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._ensure_user_directories()
        self._load_config()
    
    def _ensure_user_directories(self) -> None:
        """Create user data directory structure if it doesn't exist."""
        base_dir = Path.home() / ".bbs_p2p"
        
        # Create all required directories
        directories = [
            base_dir / "config",
            base_dir / "keys",
            base_dir / "data",
            base_dir / "logs",
            base_dir / "cache" / "attachments"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> None:
        """Load configuration from file with fallback to defaults."""
        # First, load bundled default config
        default_config = self._load_yaml(self.BUNDLED_CONFIG_PATH)
        
        # Then try to load user config
        if self.config_path.exists():
            user_config = self._load_yaml(self.config_path)
            # Merge user config over defaults
            self._config = self._merge_configs(default_config, user_config)
        else:
            # Use defaults and save to user config location
            self._config = default_config
            self.save_config()
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Validate configuration
        self._validate_config()
    
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML configuration file.
        
        Args:
            path: Path to YAML file
            
        Returns:
            Dictionary containing configuration
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if config else {}
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {path}: {e}")
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two configuration dictionaries.
        
        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration.
        
        Environment variables should be prefixed with BBS_P2P_ and use
        double underscores for nested keys. For example:
        BBS_P2P_NETWORK__LISTEN_PORT=9001
        """
        prefix = "BBS_P2P_"
        
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            
            # Remove prefix and split by double underscore
            config_key = env_key[len(prefix):].lower()
            parts = config_key.split("__")
            
            if len(parts) != 2:
                continue
            
            section, key = parts
            
            if section not in self._config:
                continue
            
            # Convert value to appropriate type
            converted_value = self._convert_env_value(env_value)
            self._config[section][key] = converted_value
    
    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable string to appropriate type.
        
        Args:
            value: String value from environment variable
            
        Returns:
            Converted value (int, bool, or str)
        """
        # Try boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _validate_config(self) -> None:
        """Validate configuration has all required fields and correct types."""
        required_sections = ['network', 'ui', 'security', 'storage', 'sync', 'logging']
        
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate network section
        network = self._config['network']
        self._validate_field(network, 'listen_port', int, 1, 65535)
        self._validate_field(network, 'enable_mdns', bool)
        self._validate_field(network, 'enable_dht', bool)
        self._validate_field(network, 'bootstrap_nodes', list)
        self._validate_field(network, 'max_peers', int, 1, 1000)
        self._validate_field(network, 'connection_timeout', int, 1, 300)
        
        # Validate UI section
        ui = self._config['ui']
        self._validate_field(ui, 'theme', str)
        self._validate_field(ui, 'enable_acrylic', bool)
        self._validate_field(ui, 'font_size', int, 8, 24)
        self._validate_field(ui, 'language', str)
        
        # Validate security section
        security = self._config['security']
        self._validate_field(security, 'key_store_path', str)
        self._validate_field(security, 'encryption_algorithm', str)
        self._validate_field(security, 'require_signature_verification', bool)
        
        # Validate storage section
        storage = self._config['storage']
        self._validate_field(storage, 'db_path', str)
        self._validate_field(storage, 'max_attachment_size', int, 1, 1073741824)
        self._validate_field(storage, 'cache_size', int, 1, 10737418240)
        
        # Validate sync section
        sync = self._config['sync']
        self._validate_field(sync, 'interval', int, 1, 3600)
        self._validate_field(sync, 'batch_size', int, 1, 1000)
        self._validate_field(sync, 'max_retries', int, 0, 10)
        
        # Validate logging section
        logging = self._config['logging']
        self._validate_field(logging, 'level', str)
        self._validate_field(logging, 'log_path', str)
        self._validate_field(logging, 'max_log_size', int, 1024, 104857600)
        self._validate_field(logging, 'backup_count', int, 0, 100)
    
    def _validate_field(self, section: Dict[str, Any], field: str, 
                       expected_type: type, min_val: Optional[int] = None, 
                       max_val: Optional[int] = None) -> None:
        """Validate a configuration field.
        
        Args:
            section: Configuration section dictionary
            field: Field name to validate
            expected_type: Expected type of the field
            min_val: Optional minimum value for numeric fields
            max_val: Optional maximum value for numeric fields
            
        Raises:
            ValueError: If validation fails
        """
        if field not in section:
            raise ValueError(f"Missing required field: {field}")
        
        value = section[field]
        
        if not isinstance(value, expected_type):
            raise ValueError(
                f"Field {field} must be of type {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )
        
        if expected_type in (int, float) and min_val is not None and value < min_val:
            raise ValueError(f"Field {field} must be >= {min_val}, got {value}")
        
        if expected_type in (int, float) and max_val is not None and value > max_val:
            raise ValueError(f"Field {field} must be <= {max_val}, got {value}")
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    def get_config(self, section: str, key: Optional[str] = None) -> Any:
        """Get configuration value.
        
        Args:
            section: Configuration section name
            key: Optional key within section. If None, returns entire section.
            
        Returns:
            Configuration value
            
        Raises:
            KeyError: If section or key doesn't exist
        """
        if section not in self._config:
            raise KeyError(f"Configuration section not found: {section}")
        
        if key is None:
            return self._config[section]
        
        if key not in self._config[section]:
            raise KeyError(f"Configuration key not found: {section}.{key}")
        
        return self._config[section][key]
    
    def set_config(self, section: str, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            section: Configuration section name
            key: Key within section
            value: Value to set
            
        Raises:
            KeyError: If section doesn't exist
        """
        if section not in self._config:
            raise KeyError(f"Configuration section not found: {section}")
        
        self._config[section][key] = value
    
    def get_network_config(self) -> NetworkConfig:
        """Get network configuration as dataclass."""
        return NetworkConfig(**self._config['network'])
    
    def get_ui_config(self) -> UIConfig:
        """Get UI configuration as dataclass."""
        return UIConfig(**self._config['ui'])
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration as dataclass."""
        return SecurityConfig(**self._config['security'])
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration as dataclass."""
        return StorageConfig(**self._config['storage'])
    
    def get_sync_config(self) -> SyncConfig:
        """Get sync configuration as dataclass."""
        return SyncConfig(**self._config['sync'])
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration as dataclass."""
        return LoggingConfig(**self._config['logging'])
    
    def expand_path(self, path: str) -> Path:
        """Expand user home directory and environment variables in path.
        
        Args:
            path: Path string potentially containing ~ or environment variables
            
        Returns:
            Expanded Path object
        """
        return Path(os.path.expanduser(os.path.expandvars(path)))


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
    """Get or create global configuration manager instance.
    
    Args:
        config_path: Optional custom path to configuration file
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    
    return _config_manager
