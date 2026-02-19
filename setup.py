"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Setup configuration for AsyncAPI Payload Validator."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

setup(
    name="asyncapi-payload-validator",
    version="1.0.0",
    description="Validate JSON payloads against AsyncAPI specifications with detailed error reporting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ingka-group/asyncapi-payload-validator",
    license="MIT",
    
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={
        "asyncapi_payload_validator": ["templates/*.j2"],
    },
    
    python_requires=">=3.8",
    install_requires=[
        "PyYAML>=6.0",
        "Jinja2>=3.1.2",
    ],
    
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
    },
    
    entry_points={
        "console_scripts": [
            "asyncapi-validate=asyncapi_payload_validator.cli:cli",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
    ],
    
    keywords="asyncapi validation json-schema event-driven api testing",
    
    project_urls={
        "Bug Reports": "https://github.com/ingka-group/asyncapi-payload-validator/issues",
        "Source": "https://github.com/ingka-group/asyncapi-payload-validator",
        "Documentation": "https://github.com/ingka-group/asyncapi-payload-validator#readme",
    },
)
