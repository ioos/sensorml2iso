import argparse
import os
import sys
from urlparse import urlparse

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
        'description': 'Parse an IOOS i52N SOS endpoint and convert SensorML to \
        ISO 19115-2 xml metadata',
        'epilog': _EPILOG,
        'formatter_class': argparse.RawDescriptionHelpFormatter,
    }
    parser = argparse.ArgumentParser(**kwargs)

    parser.add_argument('-s', '--service', type=str, required=True,
                        help='URL of SOS service to parse and convert.  Examples: {urls}'.format(urls=os.linesep.join(SOS_URLS)))

    parser.add_argument('-d', '--active_station_days', type=int, required=False, default=30,
                        help='Number of days from present to use to filter SOS stations for active/inactive designation.  Inactive are excluded from processing.')

    parser.add_argument('--stations', type=str,
                        help='Comma-separated list of station URNs to filter by. Eg. \'--stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells\'.')

    parser.add_argument('--getobs_req_hours', type=int, required=False, default=5,
                        help='Number of hours from last valid station observation time to use in GetObservation request example URLs')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose debugging mode.')

    args = parser.parse_args()

    # do some minimal arg validation:
    if args.stations is not None:
        stations = args.stations.split(",")
        print("stations len: " + str(len(stations)))
        if len(stations) == 1 and len(stations[0]) == 0:
            sys.exit("Error: '--stations' parameter value must contain comma-separated list of stations to properly filter.  Current value: {param}".format(param=stations))
    else:
        stations = None

    service_url = urlparse(args.service)
    print(service_url)
    if not service_url.scheme or not service_url.netloc:
        sys.exit("Error: '--service' parameter value must contain a valid URL.  Value passed: {param}".format(param=args.service))
    if service_url.params or service_url.query:
        sys.exit("Error: '--service' parameter should not contain query parameters ('{query}'). Please include only the GetCapabilities root URL.  Value passed: {param}".format(query=service_url.query, param=args.service))

    obj = Sensorml2Iso(
        service=args.service,
        active_station_days=args.active_station_days,
        stations=stations,
        getobs_req_hours=args.getobs_req_hours,
        verbose=args.verbose)
    obj.run()

    if args.verbose is True:
        print(obj)

# run main (hack for absence of setuptools install):
# main()
