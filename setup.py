from setuptools import setup, find_packages

setup(
    name="yuwontlaykit",
    version="0.1.0",
    packages=find_packages(include=["yuwontlaykit", "yuwontlaykit.*", "core", "core.*"]),
    py_modules=["main"],
    install_requires=[
        "colorama",
    ],
    entry_points={
        "console_scripts": [
            # guest → Yuwontlaykit: "Where did you know me? Scary huh"
            "yuwontlaykit=main:main",
            # Nikko deep → Yuwon: "Whatsup Bedis?" + Bedis tease rules
            "4782=main:main",
            # Nikko light (same character Yuwon; shallower than 4782)
            "yuwon=main:main",
        ],
    },
)
