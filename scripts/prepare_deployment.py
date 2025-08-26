#!/usr/bin/env python3
"""
Prepare QuantTime for deployment by checking git status and committing changes.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"🔄 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(f"📤 Output: {result.stdout.strip()}")
    if result.stderr:
        print(f"⚠️  Stderr: {result.stderr.strip()}")
    
    if check and result.returncode != 0:
        print(f"❌ Command failed with return code {result.returncode}")
        sys.exit(1)
    
    return result

def check_git_status():
    """Check git status and show what needs to be committed."""
    print("🔍 Checking git status...")
    
    # Check if we're in a git repo
    result = run_command(["git", "status"], check=False)
    if result.returncode != 0:
        print("❌ Not in a git repository. Please initialize git first.")
        return False
    
    # Check for uncommitted changes
    result = run_command(["git", "diff", "--quiet"], check=False)
    if result.returncode == 0:
        print("✅ No uncommitted changes found.")
        return True
    
    # Show what files have changes
    print("\n📋 Files with changes:")
    run_command(["git", "status", "--porcelain"])
    
    return False

def commit_changes():
    """Commit any uncommitted changes."""
    print("\n💾 Committing changes...")
    
    # Add all changes
    run_command(["git", "add", "."])
    
    # Check if there are changes to commit
    result = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    if result.returncode == 0:
        print("✅ No changes to commit.")
        return True
    
    # Commit with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_message = f"Auto-commit before deployment: {timestamp}"
    
    run_command(["git", "commit", "-m", commit_message])
    print("✅ Changes committed successfully.")
    return True

def main():
    """Main function."""
    print("🚀 QuantTime Deployment Preparation")
    print("=" * 40)
    
    # Check git status
    if not check_git_status():
        # Ask user if they want to commit changes
        response = input("\n❓ Do you want to commit these changes? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            commit_changes()
        else:
            print("❌ Please commit or stash your changes before deployment.")
            sys.exit(1)
    
    print("\n✅ Ready for deployment!")
    print("📋 Next steps:")
    print("1. Run: python scripts/deploy_to_r630xl.py")
    print("2. Follow the deployment instructions")

if __name__ == "__main__":
    main()
