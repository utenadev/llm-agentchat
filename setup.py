from setuptools import setup, find_packages
import os

VERSION = "0.1.0"

setup(
    name="llm-agentchat",
    description="A plugin for simonw/llm that provides a multi-agent chat environment.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="llm-agentchat contributors",
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=find_packages(),
    entry_points={"llm": ["agentchat = llm_agentchat"]},
    install_requires=[
        "llm",
        "llm-gemini",
        "fastapi",
        "uvicorn[standard]",
        "websockets",
        "PyYAML",
    ],
    python_requires=">=3.9",
)
