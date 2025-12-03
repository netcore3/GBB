# Configuration Management

This module provides configuration management for the BBS P2P Application.

## Usage

### Basic Usage

```python
from config import get_config_manager

# Get the global configuration manager instance
config = get_config_manager()

# Get a configuration value
port = config.get_config('network', 'listen_port')
theme = config.get_config('ui', 'theme')

# Get entire section
network_config = config.get_config('network')

# Set a configuration value
config.set_config('network', 'listen_port', 9001)
config.set_config('ui', 'theme', 'light')

# Save changes to file
config.save_config()
```

### Using Dataclasses

```python
from config import get_config_manager

config = get_config_manager()

# Get typed configuration objects
network = config.get_network_config()
print(f"Listening on port {network.listen_port}")
print(f"mDNS enabled: {network.enable_mdns}")

ui = config.get_ui_config()
print(f"Theme: {ui.theme}")
print(f"Font size: {ui.font_size}")
```

### Environment Variable Overrides

Configuration values can be overridden using environment variables with the prefix `BBS_P2P_`:

```bash
# Override network listen port
export BBS_P2P_NETWORK__LISTEN_PORT=9001

# Override UI theme
export BBS_P2P_UI__THEME=light

# Override boolean values
export BBS_P2P_NETWORK__ENABLE_DHT=true
```

### Path Expansion

```python
from config import get_config_manager

config = get_config_manager()

# Expand paths with ~ and environment variables
db_path = config.expand_path(config.get_config('storage', 'db_path'))
# Returns: /home/user/.bbs_p2p/data/bbs.db
```

## Configuration Structure

The configuration file is located at `~/.bbs_p2p/config/settings.yaml` and contains:

- `network`: Network settings (ports, discovery, peers)
- `ui`: User interface settings (theme, fonts)
- `security`: Security settings (keystore, encryption)
- `storage`: Storage settings (database, cache)
- `sync`: Synchronization settings (intervals, batch sizes)
- `logging`: Logging settings (levels, paths)
