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
        'lxml>=3.5.0',
        'jinja2>=2.7',
        'flake8'
        #'urllib3>=1.18'

    ],
    'version': '0.1.0',
}

setup(**kwargs)
