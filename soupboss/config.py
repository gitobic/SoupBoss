"""
Configuration management for SoupBoss.

This module provides comprehensive configuration management including:
- .env file support for environment variables
- Settings persistence and validation
- Default values and type checking
- CLI integration for config management
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dotenv import load_dotenv, set_key, unset_key
from rich.console import Console
from rich.table import Table


class ConfigManager:
    """Manages SoupBoss configuration settings and .env files."""
    
    # Default configuration values
    DEFAULT_CONFIG = {
        # Database settings
        "database": {
            "path": "data/soupboss.db",
            "backup_retention_days": 30,
            "auto_vacuum": True
        },
        
        # Ollama settings
        "ollama": {
            "host": "localhost",
            "port": 11434,
            "model": "nomic-embed-text",
            "timeout": 30,
            "max_retries": 3
        },
        
        # Export settings
        "export": {
            "default_format": "csv",
            "output_directory": ".",
            "include_timestamps": True,
            "max_results_per_export": 1000
        },
        
        # API settings
        "api": {
            "greenhouse_timeout": 30,
            "lever_timeout": 30,
            "max_jobs_per_fetch": 500,
            "rate_limit_delay": 1.0
        },
        
        # Matching settings
        "matching": {
            "similarity_threshold": 0.0,
            "max_matches_per_resume": 50,
            "score_precision": 3
        },
        
        # CLI settings
        "cli": {
            "default_table_limit": 50,
            "progress_bar": True,
            "color_output": True
        }
    }
    
    def __init__(self, config_dir: str = "."):
        self.config_dir = Path(config_dir)
        self.env_file = self.config_dir / ".env"
        self.config_file = self.config_dir / "soupboss.config.json"
        self.console = Console()
        
        # Load configuration on initialization
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from .env and config files."""
        # Start with defaults
        config = self._deep_copy_dict(self.DEFAULT_CONFIG)
        
        # Load .env file if it exists
        if self.env_file.exists():
            load_dotenv(str(self.env_file))
        
        # Load JSON config file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                config = self._merge_configs(config, file_config)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                self.console.print(f"[yellow]Warning: Could not load config file: {e}[/yellow]")
        
        # Override with environment variables
        config = self._apply_env_overrides(config)
        
        return config
    
    def _deep_copy_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._deep_copy_dict(value)
            elif isinstance(value, list):
                result[key] = value.copy()
            else:
                result[key] = value
        return result
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        result = self._deep_copy_dict(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        # Mapping of environment variables to config paths
        env_mappings = {
            # Database settings
            "SOUPBOSS_DB_PATH": ("database", "path"),
            "SOUPBOSS_DB_BACKUP_RETENTION": ("database", "backup_retention_days"),
            "SOUPBOSS_DB_AUTO_VACUUM": ("database", "auto_vacuum"),
            
            # Ollama settings
            "SOUPBOSS_OLLAMA_HOST": ("ollama", "host"),
            "SOUPBOSS_OLLAMA_PORT": ("ollama", "port"),
            "SOUPBOSS_OLLAMA_MODEL": ("ollama", "model"),
            "SOUPBOSS_OLLAMA_TIMEOUT": ("ollama", "timeout"),
            "SOUPBOSS_OLLAMA_MAX_RETRIES": ("ollama", "max_retries"),
            
            # Export settings
            "SOUPBOSS_EXPORT_FORMAT": ("export", "default_format"),
            "SOUPBOSS_EXPORT_DIR": ("export", "output_directory"),
            "SOUPBOSS_EXPORT_TIMESTAMPS": ("export", "include_timestamps"),
            "SOUPBOSS_EXPORT_MAX_RESULTS": ("export", "max_results_per_export"),
            
            # API settings
            "SOUPBOSS_GREENHOUSE_TIMEOUT": ("api", "greenhouse_timeout"),
            "SOUPBOSS_LEVER_TIMEOUT": ("api", "lever_timeout"),
            "SOUPBOSS_MAX_JOBS_FETCH": ("api", "max_jobs_per_fetch"),
            "SOUPBOSS_RATE_LIMIT": ("api", "rate_limit_delay"),
            
            # Matching settings
            "SOUPBOSS_SIMILARITY_THRESHOLD": ("matching", "similarity_threshold"),
            "SOUPBOSS_MAX_MATCHES": ("matching", "max_matches_per_resume"),
            "SOUPBOSS_SCORE_PRECISION": ("matching", "score_precision"),
            
            # CLI settings
            "SOUPBOSS_TABLE_LIMIT": ("cli", "default_table_limit"),
            "SOUPBOSS_PROGRESS_BAR": ("cli", "progress_bar"),
            "SOUPBOSS_COLOR_OUTPUT": ("cli", "color_output")
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Type conversion based on default value type
                default_value = config[section][key]
                try:
                    if isinstance(default_value, bool):
                        config[section][key] = value.lower() in ('true', '1', 'yes', 'on')
                    elif isinstance(default_value, int):
                        config[section][key] = int(value)
                    elif isinstance(default_value, float):
                        config[section][key] = float(value)
                    else:
                        config[section][key] = value
                except ValueError:
                    self.console.print(f"[yellow]Warning: Invalid value for {env_var}: {value}[/yellow]")
        
        return config
    
    def get(self, section: str, key: Optional[str] = None) -> Any:
        """Get configuration value."""
        if key is None:
            return self.config.get(section, {})
        return self.config.get(section, {}).get(key)
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """Set configuration value."""
        if section not in self.config:
            self.config[section] = {}
        
        # Validate against default structure
        if section in self.DEFAULT_CONFIG:
            if key not in self.DEFAULT_CONFIG[section]:
                self.console.print(f"[yellow]Warning: Unknown config key '{section}.{key}'[/yellow]")
        
        self.config[section][key] = value
        return self.save_config()
    
    def save_config(self) -> bool:
        """Save current configuration to JSON file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            self.console.print(f"[red]Error saving config: {e}[/red]")
            return False
    
    def set_env_var(self, key: str, value: str) -> bool:
        """Set environment variable in .env file."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            set_key(str(self.env_file), key, value)
            # Reload configuration after setting env var
            self.config = self._load_config()
            return True
        except Exception as e:
            self.console.print(f"[red]Error setting environment variable: {e}[/red]")
            return False
    
    def unset_env_var(self, key: str) -> bool:
        """Remove environment variable from .env file."""
        try:
            if self.env_file.exists():
                unset_key(str(self.env_file), key)
                # Reload configuration after unsetting env var
                self.config = self._load_config()
            return True
        except Exception as e:
            self.console.print(f"[red]Error removing environment variable: {e}[/red]")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to default values."""
        self.config = self._deep_copy_dict(self.DEFAULT_CONFIG)
        return self.save_config()
    
    def validate_config(self) -> List[str]:
        """Validate current configuration and return list of issues."""
        issues = []
        
        # Validate database path
        db_path = self.get("database", "path")
        if db_path:
            db_dir = Path(db_path).parent
            if not db_dir.exists():
                try:
                    db_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    issues.append(f"Database directory not accessible: {db_dir}")
        
        # Validate ollama settings
        ollama_port = self.get("ollama", "port")
        if not isinstance(ollama_port, int) or ollama_port < 1 or ollama_port > 65535:
            issues.append(f"Invalid Ollama port: {ollama_port}")
        
        ollama_timeout = self.get("ollama", "timeout")
        if not isinstance(ollama_timeout, (int, float)) or ollama_timeout <= 0:
            issues.append(f"Invalid Ollama timeout: {ollama_timeout}")
        
        # Validate export settings
        export_format = self.get("export", "default_format")
        if export_format not in ["csv", "json", "html"]:
            issues.append(f"Invalid export format: {export_format}")
        
        # Validate matching settings
        similarity_threshold = self.get("matching", "similarity_threshold")
        if not isinstance(similarity_threshold, (int, float)) or similarity_threshold < 0 or similarity_threshold > 1:
            issues.append(f"Invalid similarity threshold: {similarity_threshold}")
        
        return issues
    
    def display_config(self) -> None:
        """Display current configuration in a formatted table."""
        self.console.print("[bold cyan]SoupBoss Configuration[/bold cyan]")
        self.console.print()
        
        for section_name, section_data in self.config.items():
            table = Table(title=f"{section_name.title()} Settings")
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Type", style="dim")
            
            for key, value in section_data.items():
                value_str = str(value)
                if isinstance(value, bool):
                    value_str = "✓" if value else "✗"
                elif isinstance(value, str) and len(value) > 50:
                    value_str = value[:47] + "..."
                
                table.add_row(
                    key.replace("_", " ").title(),
                    value_str,
                    type(value).__name__
                )
            
            self.console.print(table)
            self.console.print()
    
    def get_env_template(self) -> str:
        """Generate a template .env file with all available settings."""
        template_lines = [
            "# SoupBoss Configuration",
            "# Copy this file to .env and modify as needed",
            "",
            "# Database Settings",
            "# SOUPBOSS_DB_PATH=data/soupboss.db",
            "# SOUPBOSS_DB_BACKUP_RETENTION=30",
            "# SOUPBOSS_DB_AUTO_VACUUM=true",
            "",
            "# Ollama Settings",
            "# SOUPBOSS_OLLAMA_HOST=localhost",
            "# SOUPBOSS_OLLAMA_PORT=11434", 
            "# SOUPBOSS_OLLAMA_MODEL=nomic-embed-text",
            "# SOUPBOSS_OLLAMA_TIMEOUT=30",
            "# SOUPBOSS_OLLAMA_MAX_RETRIES=3",
            "",
            "# Export Settings",
            "# SOUPBOSS_EXPORT_FORMAT=csv",
            "# SOUPBOSS_EXPORT_DIR=.",
            "# SOUPBOSS_EXPORT_TIMESTAMPS=true",
            "# SOUPBOSS_EXPORT_MAX_RESULTS=1000",
            "",
            "# API Settings",
            "# SOUPBOSS_GREENHOUSE_TIMEOUT=30",
            "# SOUPBOSS_LEVER_TIMEOUT=30",
            "# SOUPBOSS_MAX_JOBS_FETCH=500",
            "# SOUPBOSS_RATE_LIMIT=1.0",
            "",
            "# Matching Settings",
            "# SOUPBOSS_SIMILARITY_THRESHOLD=0.0",
            "# SOUPBOSS_MAX_MATCHES=50",
            "# SOUPBOSS_SCORE_PRECISION=3",
            "",
            "# CLI Settings",
            "# SOUPBOSS_TABLE_LIMIT=50",
            "# SOUPBOSS_PROGRESS_BAR=true",
            "# SOUPBOSS_COLOR_OUTPUT=true",
            ""
        ]
        
        return "\n".join(template_lines)
    
    def export_env_template(self, output_path: Optional[str] = None) -> bool:
        """Export .env template to file."""
        try:
            template_path = output_path or ".env.template"
            with open(template_path, 'w') as f:
                f.write(self.get_env_template())
            self.console.print(f"[green]✓ .env template exported to: {template_path}[/green]")
            return True
        except Exception as e:
            self.console.print(f"[red]Error exporting template: {e}[/red]")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for services."""
        return {
            "database": {
                "path": self.get("database", "path"),
                "exists": Path(self.get("database", "path")).exists() if self.get("database", "path") else False
            },
            "ollama": {
                "host": self.get("ollama", "host"),
                "port": self.get("ollama", "port"),
                "url": f"http://{self.get('ollama', 'host')}:{self.get('ollama', 'port')}",
                "model": self.get("ollama", "model")
            }
        }


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    if not hasattr(get_config_manager, '_instance'):
        get_config_manager._instance = ConfigManager()
    return get_config_manager._instance


def reload_config():
    """Reload configuration from files."""
    if hasattr(get_config_manager, '_instance'):
        get_config_manager._instance = ConfigManager()
    return get_config_manager()