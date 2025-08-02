"""
Setup script for Portfolio Tracker macOS App
"""
from setuptools import setup

APP = ['portfolio_gui.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'iconfile': None,  # You can add an icon file here if you have one
    'plist': {
        'CFBundleName': 'Portfolio Tracker',
        'CFBundleDisplayName': 'Portfolio Tracker',
        'CFBundleGetInfoString': "Portfolio Tracker for Crypto and Stocks",
        'CFBundleIdentifier': "com.portfolio.tracker",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHumanReadableCopyright': u"Copyright © 2024, Portfolio Tracker, All Rights Reserved"
    },
    'packages': ['pandas', 'requests'],
    'includes': ['tkinter', 'csv', 'datetime', 'pathlib', 'threading'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
) 