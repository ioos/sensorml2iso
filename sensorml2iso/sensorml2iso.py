# import urllib3
from urlparse import urlparse


# from jinja2 import Environment, PackageLoader
# env = Environment(loader=PackageLoader('yourapplication', 'templates'))


class Sensorml2Iso:
    """
    Attributes
    ----------
    server, folder, service : str
        These uniquely identify the service.
    """

    def __init__(self, service=None, verbose=False):

        self.service = service
        self.verbose = verbose

        o = urlparse(self.service)
        # o = urllib.parse.urlparse(self.server)
        self.output_directory = o.netloc

        self.run_test()
        # self.read_config_file()
        # self.load_validation_schema()

    def run_test(self):
        print("Service: {service}, verbose: {verbose}, o: {o}".format(service=self.service, verbose=self.verbose, o=self.output_directory))
