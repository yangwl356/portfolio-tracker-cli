"""
Setup script for Portfolio Tracker CLI Tool
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="portfolio-tracker-cli",
    version="1.0.0",
    author="Yangwl356",
    author_email="yangwl356@proton.me",
    description="A professional command-line tool for tracking crypto and stock investments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yangwl356/portfolio-tracker-cli",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=[
        "pandas>=1.3.0",
        "requests>=2.25.0",
        "rich>=10.0.0",
    ],
    entry_points={
        "console_scripts": [
            "portfolio=portfolio_tracker_cli.portfolio_cli:main",
        ],
    },
    keywords="portfolio, crypto, stocks, investment, tracking, cli, finance",
    project_urls={
        "Bug Reports": "https://github.com/yangwl356/portfolio-tracker-cli/issues",
        "Source": "https://github.com/yangwl356/portfolio-tracker-cli",
        "Documentation": "https://github.com/yangwl356/portfolio-tracker-cli#readme",
    },
) 