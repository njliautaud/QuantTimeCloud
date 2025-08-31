"""
Git Sync Manager for QuantTime
Handles GitHub PAT authentication, automatic pulls, and discrepancy detection
"""

import os
import json
import logging
import subprocess
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
import paramiko
import git
from git import Repo, Remote
import requests

logger = logging.getLogger(__name__)


class GitSyncManager:
    """Manages Git synchronization across all nodes with GitHub PAT authentication"""
    
    def __init__(self, github_pat: str = None, repo_path: str = None):
        self.github_pat = github_pat or os.getenv('GITHUB_PAT')
        self.repo_path = repo_path or os.getcwd()
        self.repo_url = "https://github.com/njliautaud/QuantTime.git"
        self.sync_status = {}
        self.discrepancies = {}
        
        # Initialize sync status
        self._initialize_sync_status()
    
    def _initialize_sync_status(self):
        """Initialize sync status tracking"""
        self.sync_status = {
            "last_sync": None,
            "nodes_synced": [],
            "nodes_pending": [],
            "sync_errors": [],
            "discrepancies_found": 0
        }
    
    def set_github_pat(self, pat: str):
        """Set GitHub Personal Access Token"""
        self.github_pat = pat
        logger.info("✅ GitHub PAT configured")
        
        # Test PAT validity
        if self._test_github_pat():
            logger.info("✅ GitHub PAT is valid")
            return True
        else:
            logger.error("❌ GitHub PAT is invalid")
            return False
    
    def _test_github_pat(self) -> bool:
        """Test if GitHub PAT is valid"""
        try:
            headers = {
                'Authorization': f'token {self.github_pat}',
                'Accept': 'application/vnd.github.v3+json'
            }
            response = requests.get('https://api.github.com/user', headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to test GitHub PAT: {e}")
            return False
    
    def _configure_git_credentials(self, ssh_client: paramiko.SSHClient, node_id: str):
        """Configure Git credentials on remote node"""
        try:
            # Set Git username and email
            commands = [
                f'git config --global user.name "QuantTime Sync"',
                f'git config --global user.email "sync@quanttime.local"'
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=10)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    logger.warning(f"Git config command failed on {node_id}: {cmd}")
            
            # Configure credential helper to use PAT
            if self.github_pat:
                credential_cmd = f'git config --global credential.helper "store --file ~/.git-credentials"'
                stdin, stdout, stderr = ssh_client.exec_command(credential_cmd, timeout=10)
                
                # Store PAT in credentials file
                credentials_content = f"https://{self.github_pat}:x-oauth-basic@github.com\n"
                stdin, stdout, stderr = ssh_client.exec_command(f'echo "{credentials_content}" > ~/.git-credentials', timeout=10)
                
                logger.info(f"✅ Git credentials configured on {node_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to configure Git credentials on {node_id}: {e}")
            return False
    
    def sync_node_with_github(self, node_id: str, ssh_client: paramiko.SSHClient) -> Tuple[bool, str, Dict]:
        """Sync a specific node with GitHub using PAT authentication"""
        logger.info(f"🔄 Syncing {node_id} with GitHub...")
        
        try:
            # Configure Git credentials
            if not self._configure_git_credentials(ssh_client, node_id):
                return False, "Failed to configure Git credentials", {}
            
            # Check if repo exists
            stdin, stdout, stderr = ssh_client.exec_command("ls -la /opt/quanttime/.git", timeout=10)
            repo_exists = stdout.channel.recv_exit_status() == 0
            
            if not repo_exists:
                # Clone repository
                logger.info(f"📥 Cloning repository on {node_id}...")
                clone_cmd = f"cd /opt && rm -rf quanttime && git clone {self.repo_url} quanttime"
                stdin, stdout, stderr = ssh_client.exec_command(clone_cmd, timeout=60)
                exit_status = stdout.channel.recv_exit_status()
                
                if exit_status != 0:
                    stderr_output = stderr.read().decode().strip()
                    logger.error(f"❌ Failed to clone repository on {node_id}: {stderr_output}")
                    return False, f"Clone failed: {stderr_output}", {}
                
                logger.info(f"✅ Repository cloned on {node_id}")
            else:
                # Pull latest changes
                logger.info(f"📥 Pulling latest changes on {node_id}...")
                pull_cmd = "cd /opt/quanttime && git fetch origin && git reset --hard origin/main"
                stdin, stdout, stderr = ssh_client.exec_command(pull_cmd, timeout=60)
                exit_status = stdout.channel.recv_exit_status()
                
                if exit_status != 0:
                    stderr_output = stderr.read().decode().strip()
                    logger.error(f"❌ Failed to pull changes on {node_id}: {stderr_output}")
                    return False, f"Pull failed: {stderr_output}", {}
                
                logger.info(f"✅ Repository updated on {node_id}")
            
            # Get sync info
            sync_info = self._get_node_sync_info(ssh_client, node_id)
            
            return True, f"Successfully synced {node_id} with GitHub", sync_info
            
        except Exception as e:
            logger.error(f"❌ Failed to sync {node_id}: {e}")
            return False, f"Sync failed: {str(e)}", {}
    
    def _get_node_sync_info(self, ssh_client: paramiko.SSHClient, node_id: str) -> Dict:
        """Get sync information from node"""
        try:
            sync_info = {}
            
            # Get current commit hash
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git rev-parse HEAD", timeout=10)
            sync_info["commit_hash"] = stdout.read().decode().strip()
            
            # Get last commit message
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git log -1 --pretty=format:'%s'", timeout=10)
            sync_info["last_commit"] = stdout.read().decode().strip()
            
            # Get last commit date
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git log -1 --pretty=format:'%cd' --date=iso", timeout=10)
            sync_info["last_commit_date"] = stdout.read().decode().strip()
            
            # Get branch info
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git branch --show-current", timeout=10)
            sync_info["current_branch"] = stdout.read().decode().strip()
            
            # Get status
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git status --porcelain", timeout=10)
            sync_info["local_changes"] = stdout.read().decode().strip()
            
            return sync_info
            
        except Exception as e:
            logger.error(f"Failed to get sync info from {node_id}: {e}")
            return {}
    
    def detect_sync_discrepancies(self, node_id: str, ssh_client: paramiko.SSHClient) -> Tuple[bool, List[Dict]]:
        """Detect discrepancies between node and main laptop"""
        logger.info(f"🔍 Detecting sync discrepancies for {node_id}...")
        
        try:
            discrepancies = []
            
            # Get laptop's current commit
            laptop_commit = self._get_laptop_commit_hash()
            if not laptop_commit:
                return False, [{"type": "error", "message": "Could not get laptop commit hash"}]
            
            # Get node's current commit
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git rev-parse HEAD", timeout=10)
            node_commit = stdout.read().decode().strip()
            
            # Check commit mismatch
            if laptop_commit != node_commit:
                discrepancies.append({
                    "type": "commit_mismatch",
                    "laptop_commit": laptop_commit[:8],
                    "node_commit": node_commit[:8],
                    "severity": "high"
                })
            
            # Check for local changes on node
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git status --porcelain", timeout=10)
            local_changes = stdout.read().decode().strip()
            
            if local_changes:
                discrepancies.append({
                    "type": "local_changes",
                    "changes": local_changes.split('\n'),
                    "severity": "medium"
                })
            
            # Check for untracked files
            stdin, stdout, stderr = ssh_client.exec_command("cd /opt/quanttime && git ls-files --others --exclude-standard", timeout=10)
            untracked_files = stdout.read().decode().strip().split('\n')
            
            if untracked_files and untracked_files[0]:
                discrepancies.append({
                    "type": "untracked_files",
                    "files": untracked_files,
                    "severity": "low"
                })
            
            # Check for large files not in Git
            large_files = self._detect_large_files_not_in_git(ssh_client, node_id)
            if large_files:
                discrepancies.append({
                    "type": "large_files_not_synced",
                    "files": large_files,
                    "severity": "medium"
                })
            
            # Check for missing directories
            missing_dirs = self._detect_missing_directories(ssh_client, node_id)
            if missing_dirs:
                discrepancies.append({
                    "type": "missing_directories",
                    "directories": missing_dirs,
                    "severity": "high"
                })
            
            logger.info(f"🔍 Found {len(discrepancies)} discrepancies for {node_id}")
            return True, discrepancies
            
        except Exception as e:
            logger.error(f"❌ Failed to detect discrepancies for {node_id}: {e}")
            return False, [{"type": "error", "message": str(e)}]
    
    def _get_laptop_commit_hash(self) -> Optional[str]:
        """Get current commit hash from laptop"""
        try:
            repo = Repo(self.repo_path)
            return repo.head.commit.hexsha
        except Exception as e:
            logger.error(f"Failed to get laptop commit hash: {e}")
            return None
    
    def _detect_large_files_not_in_git(self, ssh_client: paramiko.SSHClient, node_id: str) -> List[Dict]:
        """Detect large files that aren't tracked by Git"""
        try:
            large_files = []
            
            # Find files larger than 10MB that aren't in .gitignore
            cmd = """
            cd /opt/quanttime && find . -type f -size +10M -not -path './.git/*' -not -path './node_modules/*' -not -path './__pycache__/*' -not -path './.venv/*' | while read file; do
                if ! git check-ignore "$file" >/dev/null 2>&1; then
                    echo "$file"
                fi
            done
            """
            
            stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=30)
            files = stdout.read().decode().strip().split('\n')
            
            for file_path in files:
                if file_path:
                    # Get file size
                    stdin, stdout, stderr = ssh_client.exec_command(f"ls -lh '{file_path}' | awk '{{print $5}}'", timeout=10)
                    size = stdout.read().decode().strip()
                    
                    large_files.append({
                        "path": file_path,
                        "size": size,
                        "needs_sync": True
                    })
            
            return large_files
            
        except Exception as e:
            logger.error(f"Failed to detect large files on {node_id}: {e}")
            return []
    
    def _detect_missing_directories(self, ssh_client: paramiko.SSHClient, node_id: str) -> List[str]:
        """Detect directories that exist on laptop but not on node"""
        try:
            missing_dirs = []
            
            # Get laptop directories
            laptop_dirs = set()
            for root, dirs, files in os.walk(self.repo_path):
                for dir_name in dirs:
                    if not dir_name.startswith('.') and dir_name not in ['node_modules', '__pycache__', '.venv']:
                        rel_path = os.path.relpath(os.path.join(root, dir_name), self.repo_path)
                        laptop_dirs.add(rel_path)
            
            # Check each directory on node
            for dir_path in laptop_dirs:
                stdin, stdout, stderr = ssh_client.exec_command(f"test -d '/opt/quanttime/{dir_path}' && echo 'exists'", timeout=10)
                exists = stdout.read().decode().strip()
                
                if not exists:
                    missing_dirs.append(dir_path)
            
            return missing_dirs
            
        except Exception as e:
            logger.error(f"Failed to detect missing directories on {node_id}: {e}")
            return []
    
    def sync_large_files_via_sftp(self, node_id: str, ssh_client: paramiko.SSHClient, files: List[Dict]) -> bool:
        """Sync large files via SFTP that aren't tracked by Git"""
        logger.info(f"📁 Syncing {len(files)} large files to {node_id} via SFTP...")
        
        try:
            sftp = ssh_client.open_sftp()
            
            for file_info in files:
                local_path = os.path.join(self.repo_path, file_info["path"])
                remote_path = f"/opt/quanttime/{file_info['path']}"
                
                # Create remote directory if it doesn't exist
                remote_dir = os.path.dirname(remote_path)
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    sftp.mkdir(remote_dir)
                
                # Transfer file
                logger.info(f"📤 Transferring {file_info['path']} to {node_id}...")
                sftp.put(local_path, remote_path)
                
                # Set permissions
                sftp.chmod(remote_path, 0o644)
            
            sftp.close()
            logger.info(f"✅ Successfully synced {len(files)} files to {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to sync files to {node_id}: {e}")
            return False
    
    def sync_missing_directories_via_sftp(self, node_id: str, ssh_client: paramiko.SSHClient, directories: List[str]) -> bool:
        """Sync missing directories via SFTP"""
        logger.info(f"📁 Syncing {len(directories)} missing directories to {node_id}...")
        
        try:
            sftp = ssh_client.open_sftp()
            
            for dir_path in directories:
                local_dir = os.path.join(self.repo_path, dir_path)
                remote_dir = f"/opt/quanttime/{dir_path}"
                
                # Create remote directory
                try:
                    sftp.mkdir(remote_dir)
                except:
                    pass  # Directory might already exist
                
                # Copy all files in directory
                for root, dirs, files in os.walk(local_dir):
                    for file_name in files:
                        local_file = os.path.join(root, file_name)
                        rel_path = os.path.relpath(local_file, local_dir)
                        remote_file = f"{remote_dir}/{rel_path}"
                        
                        # Create subdirectories if needed
                        remote_file_dir = os.path.dirname(remote_file)
                        try:
                            sftp.stat(remote_file_dir)
                        except FileNotFoundError:
                            sftp.mkdir(remote_file_dir)
                        
                        # Transfer file
                        sftp.put(local_file, remote_file)
                        sftp.chmod(remote_file, 0o644)
            
            sftp.close()
            logger.info(f"✅ Successfully synced {len(directories)} directories to {node_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to sync directories to {node_id}: {e}")
            return False
    
    def perform_full_sync(self, node_id: str, ssh_client: paramiko.SSHClient) -> Tuple[bool, str, Dict]:
        """Perform full synchronization including Git pull and SFTP sync"""
        logger.info(f"🔄 Performing full sync for {node_id}...")
        
        sync_result = {
            "git_sync": False,
            "discrepancies_found": [],
            "files_synced": 0,
            "directories_synced": 0,
            "errors": []
        }
        
        try:
            # Step 1: Sync with GitHub
            git_success, git_message, git_info = self.sync_node_with_github(node_id, ssh_client)
            sync_result["git_sync"] = git_success
            
            if not git_success:
                sync_result["errors"].append(f"Git sync failed: {git_message}")
                return False, f"Git sync failed: {git_message}", sync_result
            
            # Step 2: Detect discrepancies
            discrepancy_success, discrepancies = self.detect_sync_discrepancies(node_id, ssh_client)
            
            if discrepancy_success:
                sync_result["discrepancies_found"] = discrepancies
                
                # Step 3: Sync large files
                large_files = [d for d in discrepancies if d["type"] == "large_files_not_synced"]
                if large_files:
                    for discrepancy in large_files:
                        if self.sync_large_files_via_sftp(node_id, ssh_client, discrepancy["files"]):
                            sync_result["files_synced"] += len(discrepancy["files"])
                        else:
                            sync_result["errors"].append(f"Failed to sync large files")
                
                # Step 4: Sync missing directories
                missing_dirs = [d for d in discrepancies if d["type"] == "missing_directories"]
                if missing_dirs:
                    for discrepancy in missing_dirs:
                        if self.sync_missing_directories_via_sftp(node_id, ssh_client, discrepancy["directories"]):
                            sync_result["directories_synced"] += len(discrepancy["directories"])
                        else:
                            sync_result["errors"].append(f"Failed to sync directories")
            
            # Update sync status
            self.sync_status["last_sync"] = datetime.now().isoformat()
            if node_id not in self.sync_status["nodes_synced"]:
                self.sync_status["nodes_synced"].append(node_id)
            
            success_message = f"Full sync completed for {node_id}"
            if sync_result["files_synced"] > 0 or sync_result["directories_synced"] > 0:
                success_message += f" (Synced {sync_result['files_synced']} files, {sync_result['directories_synced']} directories)"
            
            return True, success_message, sync_result
            
        except Exception as e:
            error_msg = f"Full sync failed for {node_id}: {str(e)}"
            sync_result["errors"].append(error_msg)
            logger.error(error_msg)
            return False, error_msg, sync_result
    
    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        return {
            "sync_status": self.sync_status,
            "discrepancies": self.discrepancies,
            "github_pat_configured": bool(self.github_pat)
        }


# Global instance
git_sync_manager = GitSyncManager()
