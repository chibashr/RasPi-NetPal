#!/usr/bin/env python3
"""
Version bumping script for Raspberry Pi Network Control Panel
Usage: python3 bump_version.py [major|minor|patch] ["Change description"]
"""

import json
import sys
import os
import datetime

def load_version_file():
    """Load the version.json file"""
    try:
        with open('../version.json', 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error: Could not load version.json: {e}")
        sys.exit(1)

def save_version_file(version_data):
    """Save the version.json file"""
    try:
        with open('../version.json', 'w') as f:
            json.dump(version_data, f, indent=2)
        print(f"Updated version.json to version {version_data['version']}")
    except IOError as e:
        print(f"Error: Could not save version.json: {e}")
        sys.exit(1)

def bump_version(version_type, changes):
    """Bump the version number and update changelog in version.json"""
    version_data = load_version_file()
    
    # Parse current version
    current = version_data['version'].split('.')
    if len(current) != 3:
        print(f"Error: Current version '{version_data['version']}' is not in semver format (major.minor.patch)")
        sys.exit(1)
    
    major, minor, patch = map(int, current)
    
    # Bump according to type
    if version_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif version_type == 'minor':
        minor += 1
        patch = 0
    elif version_type == 'patch':
        patch += 1
    else:
        print(f"Error: Unknown version bump type '{version_type}'. Use 'major', 'minor', or 'patch'")
        sys.exit(1)
    
    # Create new version string
    new_version = f"{major}.{minor}.{patch}"
    
    # Update version data
    version_data['version'] = new_version
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Add to changelog
    version_data['changelog'].insert(0, {
        "version": new_version,
        "date": today,
        "changes": changes
    })
    
    # Save updated version file
    save_version_file(version_data)
    
    return new_version

if __name__ == "__main__":
    # Make sure we're in the scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if len(sys.argv) < 2:
        print("Usage: python3 bump_version.py [major|minor|patch] [\"Change description\"] [\"Another change\"]")
        sys.exit(1)
    
    version_type = sys.argv[1].lower()
    changes = sys.argv[2:] if len(sys.argv) > 2 else ["No changes specified"]
    
    new_version = bump_version(version_type, changes)
    print(f"Version bumped to {new_version}")
    print("The changelog has been updated in version.json.")
    print("Changelog.md will be dynamically generated from this data.")
    print("\nDon't forget to restart the service for changes to take effect:")
    print("  sudo systemctl restart webpage.service") 