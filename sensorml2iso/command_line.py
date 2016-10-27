import argparse

from . import Sensorml2Iso

_EPILOG = """

"""


def main():
    """
    Command line interface
    """
    kwargs = {
        'description': 'Parse an IOOS i52N SOS endpoint and convert SensorML to \
        ISO 19115-2 xml metadata',
        'epilog': _EPILOG,
        'formatter_class': argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(**kwargs)

    help = 'URL of SOS service to parse and convert.'
    parser.add_argument('-s', '--service', type=str, required=True, help=help)

    help = 'Print folders and services as encountered.'
    parser.add_argument('-v', '--verbose', action='store_true',
                        help=help)

    """
    help = 'Resolve xlink:href attributes.'
    parser.add_argument('-r', '--resolve', action='store_true',
                        help=help)

    help = 'Skip querying a remote (AGS) service endpoint for additional \ metadata. Assume all metadata in config file or \ template.'
    parser.add_argument('--no-server-query', action='store_true',
                        help=help)

    parser.add_argument('--config-file', type=str, default='config.yaml')
    parser.add_argument('--template', type=str, default='template.xml')
    parser.add_argument('--template-category', type=str, default='nowcoast')
    """

    args = parser.parse_args()

    obj = Sensorml2Iso(
        service=args.service,
        verbose=args.verbose)
    # obj.run()
    if args.verbose is not None:
        print(obj)

# run main (hack for absence of setuptools install):
# main()
