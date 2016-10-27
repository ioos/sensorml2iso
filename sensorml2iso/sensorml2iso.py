from datetime import datetime, timedelta
# import urllib3
from urlparse import urlparse


# from jinja2 import Environment, PackageLoader
# env = Environment(loader=PackageLoader('yourapplication', 'templates'))


class Sensorml2Iso:
    """
    Attributes
    ----------
    service : str
        An IOOS DMAC-compliant SOS service to parse for active sensors to generate metadata for.
    active_sensor_days : int
        Number of days before present to designate sensors as 'active' for inclusion/exclusion purposes.
    more : str
        More class attributes...
    """

    def __init__(self, service=None, active_sensor_days=None, verbose=False):

        self.service = service

        self.active_sensor_days = active_sensor_days
        self.verbose = verbose

        o = urlparse(self.service)
        # o = urllib.parse.urlparse(self.server)
        self.output_directory = o.netloc

        self.run_test()
        # self.read_config_file()
        # self.load_validation_schema()

    def run_test(self):
        print("Service: {service}, verbose: {verbose}, o: {o}".format(service=self.service, verbose=self.verbose, o=self.output_directory))
        active_date = datetime.today() - timedelta(days=self.active_sensor_days)

        print("Date for determining active/inactive sensors in SOS service: {active_date}".format(active_date=active_date.strftime("%Y-%m-%d")))
