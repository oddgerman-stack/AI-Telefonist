import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

def get_base_dir() -> Path:
    """Return the application base directory, handling PyInstaller packaging."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    # Running in normal Python environment
    return Path(__file__).resolve().parent.parent

def get_bundle_dir() -> Path:
    """Return the read-only bundle directory containing templates and static files."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return get_base_dir()

class ConfigManager:
    """Manages application configuration, reading from config.json or fallback template."""

    def __init__(self, config_filename: str = "config.json"):
        self.base_dir = get_base_dir()
        self.bundle_dir = get_bundle_dir()
        self.config_path = self.base_dir / config_filename
        self.example_config_path = self.base_dir / "config.example.json"
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Loads configuration from file or falls back to template."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    return self._data
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}. Falling back to default.")

        if self.example_config_path.exists():
            with open(self.example_config_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
                # Auto-initialize config.json from example
                self.save()
                return self._data

        # Fallback minimal configuration
        self._data = {
            "business": {
                "name": "AI Receptionist",
                "default_language": "nl",
                "receptionist_name": "Sarah"
            },
            "pipeline": {
                "sample_rate": 16000
            },
            "storage": {
                "appointments_file": "appointments.json"
            },
            "server": {
                "host": "127.0.0.1",
                "port": 8000
            }
        }
        return self._data

    def save(self) -> None:
        """Persists current configuration to config.json."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Failed to save config: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """Access nested keys using dot notation, e.g., 'business.name'."""
        keys = key_path.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key_path: str, value: Any) -> None:
        """Set nested key using dot notation and persist."""
        keys = key_path.split(".")
        target = self._data
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self.save()

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the application base directory."""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return self.base_dir / p

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

# Global instance
config = ConfigManager()
