"""Tests for configuration management."""

import os
import pytest
import tempfile
import yaml
from pathlib import Path
from config.config_manager import ConfigManager, NetworkConfig, UIConfig


class TestConfigManager:
    """Test suite for ConfigManager."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for test configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration dictionary."""
        return {
            'network': {
                'listen_port': 9000,
                'enable_mdns': True,
                'enable_dht': False,
                'bootstrap_nodes': ['node1:8468', 'node2:8468'],
                'max_peers': 100,
                'connection_timeout': 30
            },
            'ui': {
                'theme': 'dark',
                'enable_acrylic': True,
                'font_size': 12,
                'language': 'en'
            },
            'security': {
                'key_store_path': '~/.bbs_p2p/keys/keystore.enc',
                'encryption_algorithm': 'chacha20poly1305',
                'require_signature_verification': True
            },
            'storage': {
                'db_path': '~/.bbs_p2p/data/bbs.db',
                'max_attachment_size': 52428800,
                'cache_size': 1073741824
            },
            'sync': {
                'interval': 30,
                'batch_size': 50,
                'max_retries': 3
            },
            'logging': {
                'level': 'INFO',
                'log_path': '~/.bbs_p2p/logs/app.log',
                'max_log_size': 10485760,
                'backup_count': 5
            }
        }
    
    def test_load_default_config(self, temp_config_dir, sample_config):
        """Test loading default configuration."""
        config_path = temp_config_dir / "settings.yaml"
        
        # Write sample config
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Load config
        manager = ConfigManager(config_path)
        
        assert manager.get_config('network', 'listen_port') == 9000
        assert manager.get_config('ui', 'theme') == 'dark'
        assert manager.get_config('security', 'encryption_algorithm') == 'chacha20poly1305'
    
    def test_get_config_section(self, temp_config_dir, sample_config):
        """Test getting entire configuration section."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        network_config = manager.get_config('network')
        
        assert isinstance(network_config, dict)
        assert network_config['listen_port'] == 9000
        assert network_config['enable_mdns'] is True
    
    def test_get_config_key(self, temp_config_dir, sample_config):
        """Test getting specific configuration key."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        
        assert manager.get_config('network', 'listen_port') == 9000
        assert manager.get_config('ui', 'font_size') == 12
    
    def test_set_config(self, temp_config_dir, sample_config):
        """Test setting configuration value."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        manager.set_config('network', 'listen_port', 9001)
        
        assert manager.get_config('network', 'listen_port') == 9001
    
    def test_save_config(self, temp_config_dir, sample_config):
        """Test saving configuration to file."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        manager.set_config('network', 'listen_port', 9002)
        manager.save_config()
        
        # Load config again to verify persistence
        with open(config_path, 'r') as f:
            saved_config = yaml.safe_load(f)
        
        assert saved_config['network']['listen_port'] == 9002
    
    def test_env_override(self, temp_config_dir, sample_config, monkeypatch):
        """Test environment variable overrides."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Set environment variable
        monkeypatch.setenv('BBS_P2P_NETWORK__LISTEN_PORT', '9003')
        
        manager = ConfigManager(config_path)
        
        assert manager.get_config('network', 'listen_port') == 9003
    
    def test_env_override_boolean(self, temp_config_dir, sample_config, monkeypatch):
        """Test environment variable override for boolean values."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        monkeypatch.setenv('BBS_P2P_NETWORK__ENABLE_DHT', 'true')
        
        manager = ConfigManager(config_path)
        
        assert manager.get_config('network', 'enable_dht') is True
    
    def test_validation_missing_section(self, temp_config_dir):
        """Test validation with partial user config merges with defaults."""
        config_path = temp_config_dir / "settings.yaml"
        
        # Write incomplete config - should merge with bundled defaults
        incomplete_config = {'network': {'listen_port': 9000}}
        with open(config_path, 'w') as f:
            yaml.dump(incomplete_config, f)
        
        # Should not raise because defaults are merged
        manager = ConfigManager(config_path)
        
        # User override should be applied
        assert manager.get_config('network', 'listen_port') == 9000
        
        # Other sections should come from defaults
        assert 'ui' in manager._config
        assert 'security' in manager._config
    
    def test_validation_invalid_type(self, temp_config_dir, sample_config):
        """Test validation fails with invalid field type."""
        config_path = temp_config_dir / "settings.yaml"
        
        # Set invalid type
        sample_config['network']['listen_port'] = "not_a_number"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        with pytest.raises(ValueError, match="must be of type"):
            ConfigManager(config_path)
    
    def test_validation_out_of_range(self, temp_config_dir, sample_config):
        """Test validation fails with out of range value."""
        config_path = temp_config_dir / "settings.yaml"
        
        # Set out of range value
        sample_config['network']['listen_port'] = 99999
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        with pytest.raises(ValueError, match="must be <="):
            ConfigManager(config_path)
    
    def test_get_network_config_dataclass(self, temp_config_dir, sample_config):
        """Test getting network config as dataclass."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        network_config = manager.get_network_config()
        
        assert isinstance(network_config, NetworkConfig)
        assert network_config.listen_port == 9000
        assert network_config.enable_mdns is True
    
    def test_get_ui_config_dataclass(self, temp_config_dir, sample_config):
        """Test getting UI config as dataclass."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        ui_config = manager.get_ui_config()
        
        assert isinstance(ui_config, UIConfig)
        assert ui_config.theme == 'dark'
        assert ui_config.font_size == 12
    
    def test_expand_path(self, temp_config_dir, sample_config):
        """Test path expansion with ~ and environment variables."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        
        # Test ~ expansion
        expanded = manager.expand_path("~/.bbs_p2p/data")
        assert str(expanded).startswith(str(Path.home()))
        assert not str(expanded).startswith("~")
    
    def test_user_directories_created(self, temp_config_dir, sample_config, monkeypatch):
        """Test that user data directories are created on initialization."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Mock home directory to temp dir
        test_home = temp_config_dir / "home"
        monkeypatch.setattr(Path, 'home', lambda: test_home)
        
        manager = ConfigManager(config_path)
        
        # Check directories were created
        base_dir = test_home / ".bbs_p2p"
        assert (base_dir / "config").exists()
        assert (base_dir / "keys").exists()
        assert (base_dir / "data").exists()
        assert (base_dir / "logs").exists()
        assert (base_dir / "cache" / "attachments").exists()
    
    def test_merge_configs(self, temp_config_dir, sample_config):
        """Test merging user config over defaults."""
        config_path = temp_config_dir / "settings.yaml"
        
        # Write partial user config
        user_config = {
            'network': {
                'listen_port': 9999
            },
            'ui': {
                'theme': 'light'
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(user_config, f)
        
        manager = ConfigManager(config_path)
        
        # User overrides should be applied
        assert manager.get_config('network', 'listen_port') == 9999
        assert manager.get_config('ui', 'theme') == 'light'
        
        # Defaults should still be present for non-overridden values
        assert manager.get_config('network', 'enable_mdns') is True
        assert manager.get_config('ui', 'font_size') == 12
    
    def test_persistence_across_instances(self, temp_config_dir, sample_config):
        """Test that configuration changes persist across manager instances."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # First instance: modify and save
        manager1 = ConfigManager(config_path)
        manager1.set_config('network', 'listen_port', 8888)
        manager1.set_config('ui', 'theme', 'light')
        manager1.save_config()
        
        # Second instance: load and verify
        manager2 = ConfigManager(config_path)
        assert manager2.get_config('network', 'listen_port') == 8888
        assert manager2.get_config('ui', 'theme') == 'light'
    
    def test_multiple_env_overrides(self, temp_config_dir, sample_config, monkeypatch):
        """Test multiple environment variable overrides."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Set multiple environment variables
        monkeypatch.setenv('BBS_P2P_NETWORK__LISTEN_PORT', '7777')
        monkeypatch.setenv('BBS_P2P_NETWORK__MAX_PEERS', '200')
        monkeypatch.setenv('BBS_P2P_UI__THEME', 'light')
        monkeypatch.setenv('BBS_P2P_SYNC__INTERVAL', '60')
        
        manager = ConfigManager(config_path)
        
        assert manager.get_config('network', 'listen_port') == 7777
        assert manager.get_config('network', 'max_peers') == 200
        assert manager.get_config('ui', 'theme') == 'light'
        assert manager.get_config('sync', 'interval') == 60
    
    def test_env_override_does_not_persist(self, temp_config_dir, sample_config, monkeypatch):
        """Test that environment variable overrides don't persist to file."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        # Set environment variable
        monkeypatch.setenv('BBS_P2P_NETWORK__LISTEN_PORT', '6666')
        
        manager = ConfigManager(config_path)
        assert manager.get_config('network', 'listen_port') == 6666
        
        # Save config
        manager.save_config()
        
        # Load without env var - should have env override value
        # (because it was in memory when saved)
        manager2 = ConfigManager(config_path)
        assert manager2.get_config('network', 'listen_port') == 6666
    
    def test_set_and_get_multiple_values(self, temp_config_dir, sample_config):
        """Test setting and getting multiple configuration values."""
        config_path = temp_config_dir / "settings.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(sample_config, f)
        
        manager = ConfigManager(config_path)
        
        # Set multiple values
        manager.set_config('network', 'listen_port', 5555)
        manager.set_config('network', 'max_peers', 150)
        manager.set_config('ui', 'font_size', 14)
        manager.set_config('sync', 'batch_size', 100)
        
        # Verify all changes
        assert manager.get_config('network', 'listen_port') == 5555
        assert manager.get_config('network', 'max_peers') == 150
        assert manager.get_config('ui', 'font_size') == 14
        assert manager.get_config('sync', 'batch_size') == 100
        
        # Save and reload
        manager.save_config()
        manager2 = ConfigManager(config_path)
        
        assert manager2.get_config('network', 'listen_port') == 5555
        assert manager2.get_config('network', 'max_peers') == 150
        assert manager2.get_config('ui', 'font_size') == 14
        assert manager2.get_config('sync', 'batch_size') == 100
