#!/usr/bin/env python3
"""
QuantTime Data Organization Script
Organizes the data folder by separating ES data from other data and removing unrelated files.
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('data_organization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataOrganizer:
    def __init__(self, root_dir="."):
        self.root_dir = Path(root_dir)
        self.data_dir = self.root_dir / "data"
        self.organized_dir = self.root_dir / "data_organized"
        self.backup_dir = self.root_dir / "data_backup"
        
        # Create organized directory structure
        self.es_data_dir = self.organized_dir / "es_futures"
        self.other_data_dir = self.organized_dir / "other_data"
        self.test_data_dir = self.organized_dir / "test_data"
        self.archive_dir = self.organized_dir / "archive"
        
    def create_directory_structure(self):
        """Create the organized directory structure"""
        logger.info("Creating organized directory structure...")
        
        directories = [
            self.organized_dir,
            self.es_data_dir,
            self.other_data_dir,
            self.test_data_dir,
            self.archive_dir,
            self.es_data_dir / "mbo",
            self.es_data_dir / "mbp", 
            self.es_data_dir / "trades",
            self.es_data_dir / "ohlcv",
            self.other_data_dir / "datasets",
            self.other_data_dir / "api_files",
            self.test_data_dir / "databento_test",
            self.test_data_dir / "other_test"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
    
    def identify_file_types(self, file_path):
        """Identify the type of data file"""
        file_name = file_path.name.lower()
        file_path_str = str(file_path).lower()
        
        # ES Futures data (GLBX MBO)
        if "glbx-mdp3" in file_name and ".mbo.dbn" in file_name:
            return "es_mbo"
        
        # ES Futures data (other schemas)
        if "glbx-mdp3" in file_name and any(schema in file_name for schema in [".mbp.dbn", ".trades.dbn", ".ohlcv.dbn"]):
            return "es_other"
        
        # Test data
        if "test_data" in file_name:
            return "test_data"
        
        # API files (unrelated)
        if file_name.startswith("api-v1-") or file_name.endswith(".json"):
            return "api_file"
        
        # Dataset files (unrelated)
        if file_name.endswith(".arff") or file_name.endswith(".xml"):
            return "dataset_file"
        
        # Unknown/other
        return "unknown"
    
    def organize_files(self):
        """Organize files into the proper directory structure"""
        logger.info("Starting file organization...")
        
        if not self.data_dir.exists():
            logger.error(f"Data directory {self.data_dir} does not exist!")
            return
        
        # Create backup first
        self.create_backup()
        
        # Create organized structure
        self.create_directory_structure()
        
        # Track organization results
        organization_stats = {
            "es_mbo": 0,
            "es_other": 0,
            "test_data": 0,
            "api_files": 0,
            "dataset_files": 0,
            "unknown": 0,
            "errors": 0
        }
        
        # Process all files in data directory
        for item in self.data_dir.iterdir():
            try:
                if item.is_file():
                    file_type = self.identify_file_types(item)
                    self.move_file(item, file_type)
                    organization_stats[file_type] += 1
                    
                elif item.is_dir():
                    # Handle directories
                    if "glbx-mdp3" in item.name.lower():
                        # This is ES data directory
                        self.move_es_directory(item)
                        organization_stats["es_mbo"] += 1
                    elif "test_data" in item.name.lower():
                        # This is test data directory
                        self.move_test_directory(item)
                        organization_stats["test_data"] += 1
                    else:
                        # Unknown directory
                        self.move_unknown_directory(item)
                        organization_stats["unknown"] += 1
                        
            except Exception as e:
                logger.error(f"Error processing {item}: {e}")
                organization_stats["errors"] += 1
        
        # Save organization report
        self.save_organization_report(organization_stats)
        
        logger.info("File organization completed!")
        return organization_stats
    
    def move_file(self, file_path, file_type):
        """Move a file to its appropriate directory"""
        try:
            if file_type == "es_mbo":
                dest = self.es_data_dir / "mbo" / file_path.name
            elif file_type == "es_other":
                dest = self.es_data_dir / "other" / file_path.name
            elif file_type == "test_data":
                dest = self.test_data_dir / "databento_test" / file_path.name
            elif file_type == "api_file":
                dest = self.other_data_dir / "api_files" / file_path.name
            elif file_type == "dataset_file":
                dest = self.other_data_dir / "datasets" / file_path.name
            else:
                dest = self.archive_dir / file_path.name
            
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(file_path), str(dest))
            logger.info(f"Moved {file_path.name} to {dest}")
            
        except Exception as e:
            logger.error(f"Error moving {file_path}: {e}")
            raise
    
    def move_es_directory(self, dir_path):
        """Move ES data directory to organized structure"""
        try:
            # Extract date from directory name
            date_match = None
            for part in dir_path.name.split('-'):
                if len(part) == 8 and part.isdigit():
                    date_match = part
                    break
            
            if date_match:
                # Create date-based subdirectory
                date_dir = self.es_data_dir / "mbo" / date_match
                date_dir.mkdir(parents=True, exist_ok=True)
                
                # Move contents
                for item in dir_path.iterdir():
                    dest = date_dir / item.name
                    shutil.move(str(item), str(dest))
                
                # Remove empty directory
                dir_path.rmdir()
                logger.info(f"Organized ES directory {dir_path.name} by date {date_match}")
            else:
                # Move to general ES directory
                dest = self.es_data_dir / "mbo" / dir_path.name
                shutil.move(str(dir_path), str(dest))
                logger.info(f"Moved ES directory {dir_path.name}")
                
        except Exception as e:
            logger.error(f"Error moving ES directory {dir_path}: {e}")
            raise
    
    def move_test_directory(self, dir_path):
        """Move test data directory"""
        try:
            dest = self.test_data_dir / "databento_test" / dir_path.name
            shutil.move(str(dir_path), str(dest))
            logger.info(f"Moved test directory {dir_path.name}")
        except Exception as e:
            logger.error(f"Error moving test directory {dir_path}: {e}")
            raise
    
    def move_unknown_directory(self, dir_path):
        """Move unknown directory to archive"""
        try:
            dest = self.archive_dir / dir_path.name
            shutil.move(str(dir_path), str(dest))
            logger.info(f"Moved unknown directory {dir_path.name} to archive")
        except Exception as e:
            logger.error(f"Error moving unknown directory {dir_path}: {e}")
            raise
    
    def create_backup(self):
        """Create a backup of the original data directory"""
        logger.info("Creating backup of original data directory...")
        
        if self.data_dir.exists():
            backup_path = self.backup_dir / f"data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copytree(self.data_dir, backup_path)
            logger.info(f"Backup created at: {backup_path}")
    
    def save_organization_report(self, stats):
        """Save organization statistics"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "directory_structure": {
                "es_data": str(self.es_data_dir),
                "other_data": str(self.other_data_dir),
                "test_data": str(self.test_data_dir),
                "archive": str(self.archive_dir)
            }
        }
        
        report_path = self.organized_dir / "organization_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Organization report saved to: {report_path}")
    
    def create_symlinks(self):
        """Create symlinks for backward compatibility"""
        logger.info("Creating symlinks for backward compatibility...")
        
        # Create symlink from old data directory to new organized structure
        if self.data_dir.exists():
            # Rename old data directory
            old_data = self.root_dir / "data_old"
            self.data_dir.rename(old_data)
        
        # Create symlink
        try:
            os.symlink(self.organized_dir, self.data_dir)
            logger.info(f"Created symlink: {self.data_dir} -> {self.organized_dir}")
        except Exception as e:
            logger.error(f"Error creating symlink: {e}")
    
    def update_configurations(self):
        """Update configuration files to point to new data structure"""
        logger.info("Updating configuration files...")
        
        # Update data manager configuration
        config_files = [
            "quanttime/data/data_manager.py",
            "quanttime/adapter/databento_mbo.py",
            "quanttime/data/pipeline.py"
        ]
        
        for config_file in config_files:
            config_path = self.root_dir / config_file
            if config_path.exists():
                self.update_config_file(config_path)
    
    def update_config_file(self, file_path):
        """Update a configuration file to use new data paths"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Update data paths
            content = content.replace(
                'data_dir = "data"',
                'data_dir = "data_organized/es_futures"'
            )
            content = content.replace(
                'root_data_dir="data"',
                'root_data_dir="data_organized/es_futures"'
            )
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            logger.info(f"Updated configuration file: {file_path}")
            
        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")

def main():
    """Main function to organize data"""
    print("=" * 60)
    print("QuantTime Data Organization Script")
    print("=" * 60)
    
    organizer = DataOrganizer()
    
    print("\nThis script will:")
    print("1. Create a backup of your current data directory")
    print("2. Organize data into a clean structure:")
    print("   - ES Futures data (GLBX MBO/MBP/Trades/OHLCV)")
    print("   - Test data")
    print("   - Other unrelated files (moved to archive)")
    print("3. Create symlinks for backward compatibility")
    print("4. Update configuration files")
    
    response = input("\nDo you want to proceed? (y/N): ").strip().lower()
    if response != 'y':
        print("Operation cancelled.")
        return
    
    try:
        # Organize the data
        stats = organizer.organize_files()
        
        # Create symlinks
        organizer.create_symlinks()
        
        # Update configurations
        organizer.update_configurations()
        
        print("\n" + "=" * 60)
        print("DATA ORGANIZATION COMPLETED!")
        print("=" * 60)
        print(f"\nOrganization Statistics:")
        print(f"  ES MBO Files: {stats['es_mbo']}")
        print(f"  ES Other Files: {stats['es_other']}")
        print(f"  Test Data Files: {stats['test_data']}")
        print(f"  API Files: {stats['api_files']}")
        print(f"  Dataset Files: {stats['dataset_files']}")
        print(f"  Unknown Files: {stats['unknown']}")
        print(f"  Errors: {stats['errors']}")
        
        print(f"\nNew Directory Structure:")
        print(f"  ES Data: {organizer.es_data_dir}")
        print(f"  Other Data: {organizer.other_data_dir}")
        print(f"  Test Data: {organizer.test_data_dir}")
        print(f"  Archive: {organizer.archive_dir}")
        print(f"  Backup: {organizer.backup_dir}")
        
        print(f"\nYour ES data is now organized in: {organizer.es_data_dir}")
        print("The old 'data' directory now points to the organized structure.")
        print("All original files are backed up in the 'data_backup' directory.")
        
    except Exception as e:
        logger.error(f"Error during organization: {e}")
        print(f"\nERROR: {e}")
        print("Check the log file 'data_organization.log' for details.")

if __name__ == "__main__":
    main()
