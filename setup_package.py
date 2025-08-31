#!/usr/bin/env python3
"""
QuantTime Setup Script
Standard Python package setup for QuantTime

This script provides:
1. Package metadata and dependencies
2. Installation configuration
3. Development setup
4. Entry points for command-line tools

Usage:
    pip install -e .          # Install in development mode
    python setup.py install   # Install in production mode
    python setup.py develop   # Install in development mode
"""

from setuptools import setup, find_packages
from pathlib import Path
import os

# Read the README file
def read_readme():
    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding='utf-8')
    return "QuantTime ML Trading Suite"

# Read requirements from requirements.txt
def read_requirements():
    requirements_path = Path(__file__).parent / "requirements.txt"
    if requirements_path.exists():
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

# Get package version
def get_version():
    version_file = Path(__file__).parent / "quanttime" / "__init__.py"
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('__version__'):
                    return line.split('=')[1].strip().strip('"\'')
    return "0.1.0"

# Package configuration
setup(
    name="quanttime",
    version=get_version(),
    author="QuantTime Team",
    author_email="team@quanttime.com",
    description="A comprehensive quantitative trading platform for MBO Level 3 data analysis",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/QuantTime",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/QuantTime/issues",
        "Source": "https://github.com/yourusername/QuantTime",
        "Documentation": "https://github.com/yourusername/QuantTime/docs",
    },
    packages=find_packages(include=["quanttime", "quanttime.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.11",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "docs": [
            "sphinx>=6.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "myst-parser>=1.0.0",
        ],
        "full": [
            "torch>=2.0.0",
            "transformers>=4.30.0",
            "stable-baselines3>=2.0.0",
            "optuna>=3.0.0",
            "lightgbm>=4.0.0",
            "xgboost>=1.7.0",
            "catboost>=1.2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "quanttime=quanttime.cli:main",
            "quanttime-dashboard=quanttime.dashboard.app:main",
            "quanttime-setup=scripts.setup_project:main",
            "quanttime-deploy=scripts.deploy_nodes:main",
        ],
    },
    include_package_data=True,
    package_data={
        "quanttime": [
            "config/*.json",
            "config/*.yaml",
            "config/*.yml",
            "data/**/*",
            "models/**/*",
            "docs/**/*",
        ],
    },
    zip_safe=False,
    keywords=[
        "trading",
        "quantitative",
        "finance",
        "machine-learning",
        "backtesting",
        "databento",
        "mbo",
        "orderflow",
        "ray",
        "distributed-computing",
    ],
)
