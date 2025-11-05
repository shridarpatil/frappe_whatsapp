"""This script is used to package `kreo_whats2` Frappe application.

It uses setuptools to define package metadata and find all necessary
packages and data files for distribution. This allows app to be installed,
upgraded, and uninstalled using standard Python packaging tools.
"""
from setuptools import setup, find_packages

setup(
    name="kreo_whats2",
    version="1.0.0",
    description="WhatsApp integration for Kreo project.",
    author="Kreo",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)