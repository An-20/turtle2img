# -*- coding: utf-8 -*-
from distutils.core import setup


def get_readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="canvasvg",
    version="1.0.6",
    description="Save Tkinter Canvas in SVG file",
    author="An-20",
    url="https://github.com/An-20/turtle2img",
    license="BSD (3 clauses)",
    long_description=get_readme(),
    packages=["canvasvg"],
    package_dir={"canvasvg": "src"},
    keywords=[
        "turtle",
        "image",
        "png",
        "jpg"
    ],
    install_requires=[
        "CairoSVG",
        "Pillow"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Multimedia :: Graphics :: Capture :: Screen Capture",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
    ],
)
