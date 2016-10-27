from setuptools import setup

kwargs = {
    'name': 'sensorml2iso',
    'author': 'Micah Wengren',
    'author_email': 'micah.wengren@gmail.com',
    'url': 'https://github.com/mwengren/sensorml2iso',
    'description': 'A small utility to convert IOOS SOS SensorML to ISO19115-2 for IOOS Catalog',
    'entry_points': {
        'console_scripts': [
            'sensorml2iso=sensorml2iso.command_line:main',
        ]
    },
    'packages': ['sensorml2iso'],
    'package_data': {
        'templates': [
            '*.xml'
        ]
    },
    'install_requires': [
        'OWSLib>=0.11.0',
        'flake8>=3.0.4',
        'geopandas>=0.2.1',
        'jinja2>=2.7',
        'lxml>=3.5.0',
        'numpy>=1.11.2',
        'pandas>=0.19.0',
        'pyoos>=0.8.2',
        'shapely>=1.5.17'


        #'urllib3>=1.18'

    ],
    'version': '0.1.0',
}

setup(**kwargs)
