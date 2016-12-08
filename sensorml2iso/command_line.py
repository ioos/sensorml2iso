import argparse
import os
import sys
try:
    from urllib.parse import urlparse  # Python 3
except ImportError:
    from urlparse import urlparse  # Python 2
from . import Sensorml2Iso

_EPILOG = """

"""

SOS_URLS = [
    'http://sos.aoos.org/sos/sos/kvp',
    'http://sos.cencoos.org/sos/sos/kvp',
    'http://data.gcoos.org:8080/52nSOS/sos/kvp',
    'http://sos.glos.us/52n/sos/kvp',
    'http://data.nanoos.org/52nsos/sos/kvp',
    'http://opendap.co-ops.nos.noaa.gov/ioos-dif-sos/SOS',
    'http://sdf.ndbc.noaa.gov/sos/server.php'
]


def main():
    """
    Command line interface
    """
    kwargs = {
        'description': 'Parse an IOOS i52N SOS endpoint and convert SensorML to ISO 19115-2 xml metadata',
        'epilog': _EPILOG,
        'formatter_class': argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(**kwargs)

    parser.add_argument('-s', '--service', type=str, required=True,
                        help='URL of SOS service to parse and convert.  Examples: {urls}'.format(urls=os.linesep.join(SOS_URLS)))

    parser.add_argument('-d', '--active_station_days', type=int, required=False, default=None,
                        help='Number of days from present to use to filter SOS stations not actively reporting observations for active/inactive designation.  Inactive stations are excluded from processing.')

    parser.add_argument('--stations', type=str,
                        help='Comma-separated list of station URNs to filter by. Eg. \'--stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells\'.')

    parser.add_argument('--getobs_req_hours', type=int, required=False, default=2,
                        help='Number of hours from last valid station observation time to use in GetObservation request example URLs.  Default: 2.')

    parser.add_argument('--response_formats', type=str, required=False, default='application/json,text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"',
                        help='Comma-separated list of SOS responseFormats to use in creating GetObservation download links for each observed parameter.  Eg. \'--response_formats=application/json,application/zip; subtype=x-netcdf\'.  Default: [\'application/json\', \'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"\'].')

    parser.add_argument('--sos_type', type=str, required=False, default='ioos',
                        help='Name of SOS implementation type [ioos|ndbc|coops].  This is not implemented currently, placeholder for differing SOS behavior, if necessary.  Default: \'ioos\'.')

    parser.add_argument('--output_dir', type=str,
                        help='Specify an output directory (relative to current working directory) to write ISO 19115-2 XML files to.  If omitted \
                        the default output directory will a subdirectory using the domain name of the SOS service URL passed \
                        (eg. sos.gliders.ioos.us).')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose debugging mode.')

    args = parser.parse_args()

    # do some minimal arg validation:
    if args.stations is not None:
        stations = args.stations.split(",")
        if len(stations) == 1 and len(stations[0]) == 0:
            sys.exit("Error: '--stations' parameter value must contain comma-separated list of stations to properly filter.  Current value: {param}".format(param=stations))
    else:
        stations = None

    if args.response_formats is not None:
        response_formats = args.response_formats.split(",")
        if len(response_formats) == 1 and len(response_formats[0]) == 0:
            sys.exit("Error: '--response_formats' parameter value must contain comma-separated list of formats to properly filter.  Current value: {param}".format(param=stations))
    else:
        response_formats = None

    if args.sos_type.lower() not in ['ioos', 'ndbc', 'coops']:
        sys.exit("Error: '--sos_type' parameter value must be one of 'ioos', 'ndbc', or 'coops'.  Value passed: {param}".format(param=args.sos_type))

    service_url = urlparse(args.service)
    # print(service_url)
    if not service_url.scheme or not service_url.netloc:
        sys.exit("Error: '--service' parameter value must contain a valid URL.  Value passed: {param}".format(param=args.service))
    if service_url.params or service_url.query:
        sys.exit("Error: '--service' parameter should not contain query parameters ('{query}'). Please include only the service endpoint URL.  Value passed: {param}".format(query=service_url.query, param=args.service))

    obj = Sensorml2Iso(
        service=args.service,
        active_station_days=args.active_station_days,
        stations=stations,
        getobs_req_hours=args.getobs_req_hours,
        response_formats=response_formats,
        sos_type=args.sos_type.lower(),
        output_dir=args.output_dir,
        verbose=args.verbose)
    obj.run()

    if args.verbose is True:
        print(obj)

# run main (hack for absence of setuptools install):
# main()
