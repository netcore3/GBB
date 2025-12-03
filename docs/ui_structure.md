# UI Structure Documentation

## Main Window Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  P2P Encrypted BBS                                    [_][□][X] │
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                       │
│  [📁]    │                                                       │
│  Boards  │                                                       │
│          │                                                       │
│  [💬]    │                                                       │
│  Chats   │          Content Area (StackedWidget)                │
│          │                                                       │
│  [👥]    │          Current Page Displayed Here                 │
│  Peers   │                                                       │
│          │                                                       │
│          │                                                       │
│          │                                                       │
│          │                                                       │
│  ─────   │                                                       │
│          │                                                       │
│  [⚙️]    │                                                       │
│  Settings│                                                       │
│          │                                                       │
│  [ℹ️]    │                                                       │
│  About   │                                                       │
│          │                                                       │
└──────────┴──────────────────────────────────────────────────────┘
```

## Navigation Structure

### Top Navigation Items
1. **Boards** (📁 FluentIcon.FOLDER)
   - Purpose: Browse and manage discussion boards
   - Status: Placeholder (ready for BoardListPage)

2. **Private Chats** (💬 FluentIcon.CHAT)
   - Purpose: View and manage private conversations
   - Status: Placeholder (ready for ChatListPage)

3. **Peers** (👥 FluentIcon.PEOPLE)
   - Purpose: Monitor connected peers and network status
   - Status: Placeholder (ready for PeerMonitorPage)

### Bottom Navigation Items
4. **Settings** (⚙️ FluentIcon.SETTING)
   - Purpose: Configure application settings
   - Status: **Fully Implemented** (SettingsPage)

5. **About** (ℹ️ FluentIcon.INFO)
   - Purpose: Display application information
   - Status: Placeholder (ready for AboutPage)

## Settings Page Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  Settings                                                        │
│                                                                  │
│  ┌─ User Interface ──────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  🖌️ Theme                                                  │  │
│  │     Choose application theme          [Dark ▼]            │  │
│  │                                                            │  │
│  │  🔤 Font Size                                              │  │
│  │     Adjust text size                  [━━●━━━] 12         │  │
│  │                                                            │  │
│  │  ⬜ Acrylic Effect                                         │  │
│  │     Enable translucent window effect  [ON/OFF]            │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Network ──────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  📡 Enable mDNS Discovery                                  │  │
│  │     Automatically discover peers      [ON/OFF]            │  │
│  │                                                            │  │
│  │  🌐 Enable DHT Discovery                                   │  │
│  │     Discover peers globally           [ON/OFF]            │  │
│  │                                                            │  │
│  │  🔌 Listen Port                                            │  │
│  │     Network port for connections      [━━━●━━] 9000       │  │
│  │                                                            │  │
│  │  👥 Maximum Peers                                          │  │
│  │     Max simultaneous connections      [━━━●━━] 100        │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Security ─────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  💾 Export Identity                                        │  │
│  │     Backup your identity              [Export]            │  │
│  │                                                            │  │
│  │  📁 Import Identity                                        │  │
│  │     Restore from backup               [Import]            │  │
│  │                                                            │  │
│  │  📜 Require Signature Verification                         │  │
│  │     Reject invalid signatures         [ON/OFF]            │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Storage ──────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  📁 Database Location                                      │  │
│  │     ~/.bbs_p2p/data/bbs.db            [Open]              │  │
│  │                                                            │  │
│  │  📄 Max Attachment Size (MB)                               │  │
│  │     Maximum file size                 [━━━●━━] 50 MB      │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Synchronization ──────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  🔄 Sync Interval (seconds)                                │  │
│  │     How often to sync                 [━━━●━━] 30s        │  │
│  │                                                            │  │
│  │  📦 Batch Size                                             │  │
│  │     Posts to sync at once             [━━━●━━] 50         │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│                      [Save Settings]                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Notification System

InfoBar notifications appear in the top-right corner:

```
┌─────────────────────────────────────────────────────────────────┐
│                                    ┌─────────────────────────┐  │
│                                    │ ✓ Settings Saved        │  │
│                                    │   Configuration saved   │  │
│                                    │                      [X]│  │
│                                    └─────────────────────────┘  │
│                                                                  │
```

### Notification Types
- **Success** (✓ green): Successful operations
- **Error** (✗ red): Failed operations
- **Warning** (⚠ yellow): Important notices
- **Info** (ℹ blue): General information

## Theme Support

### Dark Theme (Default)
- Dark background with light text
- Fluent Design acrylic effects
- Modern, sleek appearance

### Light Theme
- Light background with dark text
- Fluent Design acrylic effects
- Clean, bright appearance

### Theme Switching
- Instant theme changes via Settings
- No restart required
- Theme persists across sessions

## Asyncio Integration

The main window integrates Python's asyncio with Qt's event loop:

```python
# Schedule async operation from UI
self.event_loop.run_coroutine(
    self.network_manager.connect_to_peer(address, port)
)

# UI remains responsive during async operations
```

### Event Loop Processing
- Processes asyncio events every 10ms
- Non-blocking network operations
- Smooth UI interactions
- Proper cleanup on window close

## Signal/Slot Architecture

```
MainWindow
    │
    ├─→ theme_changed (Signal)
    │   └─→ Connected to: apply_theme()
    │
    ├─→ navigation_changed (Signal)
    │   └─→ Emitted when: Navigation item selected
    │
    └─→ SettingsPage
        ├─→ theme_changed (Signal)
        │   └─→ Connected to: MainWindow.apply_theme()
        │
        └─→ settings_saved (Signal)
            └─→ Connected to: MainWindow._on_settings_saved()
```

## Manager Integration

The main window accepts optional manager instances:

```python
MainWindow(
    config_manager=config_manager,  # Required
    board_manager=board_manager,    # Optional
    thread_manager=thread_manager,  # Optional
    chat_manager=chat_manager       # Optional
)
```

Managers are stored and available for page widgets to use.

## Page Replacement

Placeholder pages can be replaced with actual implementations:

```python
# Create actual page
boards_page = BoardListPage(
    board_manager=window.board_manager,
    parent=window
)

# Replace placeholder
window.set_boards_page(boards_page)
```

## File Structure

```
ui/
├── __init__.py              # Module exports
├── main_window.py           # MainWindow class
├── settings_page.py         # SettingsPage class
└── demo_main_window.py      # Demo/test script
```

## Dependencies

- **PySide6** (>=6.6.0): Qt framework for Python
- **PySide6-Fluent-Widgets** (>=1.5.0): Fluent Design components
- **PyYAML** (>=6.0.0): Configuration file handling

## Running the Demo

```bash
# Install dependencies
pip install -r requirements.txt

# Run the demo
python ui/demo_main_window.py
```

The demo launches the main window with:
- All navigation items functional
- Settings page fully operational
- Theme switching working
- Placeholder pages visible

## Next Implementation Steps

1. **BoardListPage** - Display and manage boards
2. **ThreadListPage** - Display threads in a board
3. **PostViewPage** - Display posts in a thread
4. **ChatListPage** - Display private conversations
5. **ChatWidget** - Chat interface
6. **PeerMonitorPage** - Display connected peers
7. **AboutPage** - Application information
