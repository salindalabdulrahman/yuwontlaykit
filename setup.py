from setuptools import setup, find_packages

setup(
    name="yuwontlaykit",
    version="0.1.0",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "colorama",
    ],
    entry_points={
        "console_scripts": [
            "yuwontlaykit=main:main",
        ],
    },
)
