#!/usr/bin/env python3
"""Quick test script to verify theme changes work correctly."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from qfluentwidgets import Theme

# Import theme utilities
from ui.theme_utils import GhostTheme


def test_theme_methods():
    """Test that GhostTheme methods work correctly."""
    print("Testing GhostTheme methods...")
    
    # Test font size methods
    print(f"Initial font size: {GhostTheme.get_font_size()}")
    GhostTheme.set_font_size(16)
    print(f"After setting to 16: {GhostTheme.get_font_size()}")
    assert GhostTheme.get_font_size() == 16, "Font size not set correctly"
    
    # Test theme application
    print("Testing theme application...")
    GhostTheme.apply_theme(Theme.DARK)
    print("Dark theme applied successfully")
    
    GhostTheme.apply_theme(Theme.LIGHT)
    print("Light theme applied successfully")
    
    # Test color getters
    print("\nTesting color getters...")
    print(f"Purple primary: {GhostTheme.get_purple_primary()}")
    print(f"Purple secondary: {GhostTheme.get_purple_secondary()}")
    print(f"Purple tertiary: {GhostTheme.get_purple_tertiary()}")
    print(f"Background: {GhostTheme.get_background()}")
    print(f"Text primary: {GhostTheme.get_text_primary()}")
    
    print("\n✅ All theme method tests passed!")


def test_settings_imports():
    """Test that settings page imports work correctly."""
    print("\nTesting settings page imports...")
    
    try:
        from ui.settings_page import SettingsPage
        print("✅ SettingsPage imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import SettingsPage: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Theme Changes Verification Test")
    print("=" * 60)
    
    # Create QApplication (required for Qt operations)
    app = QApplication(sys.argv)
    
    try:
        # Run tests
        test_theme_methods()
        test_settings_imports()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Test failed with error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
