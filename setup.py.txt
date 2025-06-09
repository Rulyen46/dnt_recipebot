#!/usr/bin/env python3
"""
Setup script for EverQuest Crafting Bot
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Ensure Python 3.8+ is being used"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✓ Python version: {sys.version}")

def install_requirements():
    """Install required packages"""
    print("Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Requirements installed successfully")
    except subprocess.CalledProcessError:
        print("Error: Failed to install requirements")
        sys.exit(1)

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    env_file = Path(".env")
    template_file = Path(".env.template")
    
    if not env_file.exists() and template_file.exists():
        print("Creating .env file from template...")
        template_file.rename(env_file)
        print("✓ .env file created")
        print("⚠️  Please edit .env file and add your Discord bot token")
    elif env_file.exists():
        print("✓ .env file already exists")
    else:
        print("⚠️  No .env template found")

def create_log_directory():
    """Create logs directory if it doesn't exist"""
    log_dir = Path("logs")
    if not log_dir.exists():
        log_dir.mkdir()
        print("✓ Logs directory created")

def main():
    """Main setup function"""
    print("EverQuest Crafting Bot Setup")
    print("=" * 30)
    
    check_python_version()
    install_requirements()
    create_env_file()
    create_log_directory()
    
    print("\n" + "=" * 30)
    print("Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file and add your Discord bot token")
    print("2. Add your forum ID to WATCHED_FORUM_ID in .env")
    print("3. Run the bot with: python eq_crafting_bot.py")
    print("4. Users can now create forum posts for automatic recipe responses!")

if __name__ == "__main__":
    main()