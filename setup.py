from setuptools import setup


reqs = [line.strip() for line in open('requirements.txt')]


kwargs = {
    "name": "sensorml2iso",
    "author": "Micah Wengren",
    "author_email": "micah.wengren@gmail.com",
    "url": "https://github.com/ioos/sensorml2iso",
    "description": "A small utility to convert IOOS SOS SensorML to ISO19115-2 for IOOS Catalog",
    "entry_points": {
        "console_scripts": [
            "sensorml2iso=sensorml2iso.command_line:main",
        ]
    },
    "classifiers": [
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.5",
        "Topic :: Documentation :: Sphinx",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: GIS"
    ],
    "packages": ["sensorml2iso"],
    "package_data": {
        "templates": [
            "*.xml"
        ]
    },
    "version": "1.0.2",
}


# It was kind of convenient to keep kwargs as a fully compliant JSON structure so I'll move install requires below it


kwargs['install_requires'] = reqs


setup(**kwargs)
