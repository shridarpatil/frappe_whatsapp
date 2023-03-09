from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in frappe_whatsapp/__init__.py
from frappe_whatsapp import __version__ as version

setup(
    name="frappe_whatsapp",
    version=version,
    description="WhatsApp integration for frappe",
    author="Shridhar Patil",
    author_email="shridhar.p@zerodha.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
