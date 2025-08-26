#!/usr/bin/env python3
"""
Automated Git Sync Script
Automatically commits and pushes code changes to keep nodes synchronized
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_git_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoGitSync:
    """Automated Git synchronization manager"""
    
    def __init__(self, repo_path: str = None):
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.git_path = self.repo_path / ".git"
        
        if not self.git_path.exists():
            raise ValueError(f"Not a Git repository: {self.repo_path}")
        
        logger.info(f"Initialized AutoGitSync for: {self.repo_path}")
    
    def run_command(self, command: str, cwd: Path = None) -> tuple:
        """Run a shell command and return (success, output)"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd or self.repo_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {command} - {e}")
            return False, str(e)
    
    def check_git_status(self) -> dict:
        """Check Git status and return status information"""
        status = {
            "has_changes": False,
            "staged_files": [],
            "unstaged_files": [],
            "untracked_files": [],
            "branch": "",
            "remote": ""
        }
        
        # Get current branch
        success, output = self.run_command("git branch --show-current")
        if success:
            status["branch"] = output
        
        # Get remote
        success, output = self.run_command("git remote get-url origin")
        if success:
            status["remote"] = output
        
        # Get status
        success, output = self.run_command("git status --porcelain")
        if success and output:
            status["has_changes"] = True
            
            for line in output.split('\n'):
                if line.strip():
                    file_status = line[:2]
                    file_path = line[3:]
                    
                    if file_status.startswith('A') or file_status.startswith('M'):
                        status["staged_files"].append(file_path)
                    elif file_status.startswith(' M') or file_status.startswith(' D'):
                        status["unstaged_files"].append(file_path)
                    elif file_status.startswith('??'):
                        status["untracked_files"].append(file_path)
        
        return status
    
    def auto_commit(self, message: str = None) -> bool:
        """Automatically commit changes"""
        if not message:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Auto-sync: {timestamp}"
        
        # Add all changes
        success, output = self.run_command("git add .")
        if not success:
            logger.error(f"Failed to add files: {output}")
            return False
        
        # Check if there are staged changes
        success, output = self.run_command("git diff --cached --name-only")
        if not success or not output.strip():
            logger.info("No changes to commit")
            return True
        
        # Commit changes
        success, output = self.run_command(f'git commit -m "{message}"')
        if not success:
            logger.error(f"Failed to commit: {output}")
            return False
        
        logger.info(f"Committed changes: {message}")
        return True
    
    def auto_push(self) -> bool:
        """Automatically push changes to remote"""
        # Get current branch
        success, output = self.run_command("git branch --show-current")
        if not success:
            logger.error("Failed to get current branch")
            return False
        
        branch = output.strip()
        
        # Push to remote
        success, output = self.run_command(f"git push origin {branch}")
        if not success:
            logger.error(f"Failed to push: {output}")
            return False
        
        logger.info(f"Pushed changes to origin/{branch}")
        return True
    
    def auto_pull(self) -> bool:
        """Automatically pull changes from remote"""
        # Get current branch
        success, output = self.run_command("git branch --show-current")
        if not success:
            logger.error("Failed to get current branch")
            return False
        
        branch = output.strip()
        
        # Pull from remote
        success, output = self.run_command(f"git pull origin {branch}")
        if not success:
            logger.error(f"Failed to pull: {output}")
            return False
        
        logger.info(f"Pulled changes from origin/{branch}")
        return True
    
    def sync_changes(self, auto_push: bool = True, auto_pull: bool = True) -> bool:
        """Sync changes with remote repository"""
        try:
            # Check status
            status = self.check_git_status()
            
            if status["has_changes"]:
                logger.info(f"Found changes: {len(status['staged_files'])} staged, "
                          f"{len(status['unstaged_files'])} unstaged, "
                          f"{len(status['untracked_files'])} untracked")
                
                # Commit changes
                if not self.auto_commit():
                    return False
            
            # Push changes if requested
            if auto_push:
                if not self.auto_push():
                    return False
            
            # Pull changes if requested
            if auto_pull:
                if not self.auto_pull():
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
    
    def watch_and_sync(self, interval: int = 60, auto_push: bool = True, auto_pull: bool = True):
        """Watch for changes and automatically sync"""
        logger.info(f"Starting watch mode - checking every {interval} seconds")
        
        try:
            while True:
                logger.info("Checking for changes...")
                
                if self.sync_changes(auto_push, auto_pull):
                    logger.info("Sync completed successfully")
                else:
                    logger.warning("Sync completed with warnings")
                
                logger.info(f"Waiting {interval} seconds before next check...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Watch mode stopped by user")
        except Exception as e:
            logger.error(f"Watch mode failed: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Automated Git Sync Tool")
    parser.add_argument("--repo", help="Repository path (default: current directory)")
    parser.add_argument("--watch", action="store_true", help="Watch mode - continuously sync")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds (default: 60)")
    parser.add_argument("--no-push", action="store_true", help="Don't push changes")
    parser.add_argument("--no-pull", action="store_true", help="Don't pull changes")
    parser.add_argument("--message", help="Custom commit message")
    parser.add_argument("--status", action="store_true", help="Show Git status and exit")
    
    args = parser.parse_args()
    
    try:
        # Initialize sync manager
        sync = AutoGitSync(args.repo)
        
        # Show status if requested
        if args.status:
            status = sync.check_git_status()
            print(f"Repository: {sync.repo_path}")
            print(f"Branch: {status['branch']}")
            print(f"Remote: {status['remote']}")
            print(f"Has Changes: {status['has_changes']}")
            print(f"Staged Files: {len(status['staged_files'])}")
            print(f"Unstaged Files: {len(status['unstaged_files'])}")
            print(f"Untracked Files: {len(status['untracked_files'])}")
            return
        
        # Run in watch mode or single sync
        if args.watch:
            sync.watch_and_sync(
                interval=args.interval,
                auto_push=not args.no_push,
                auto_pull=not args.no_pull
            )
        else:
            # Single sync
            if sync.sync_changes(
                auto_push=not args.no_push,
                auto_pull=not args.no_pull
            ):
                logger.info("Sync completed successfully")
                sys.exit(0)
            else:
                logger.error("Sync failed")
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Failed to initialize sync: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
