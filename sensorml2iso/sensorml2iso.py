from datetime import datetime, timedelta
# import urllib3
from urllib import urlencode
from urlparse import urlparse
from collections import OrderedDict
from lxml import etree

import numpy as np
import pandas as pd
from shapely.geometry import Point
import geopandas as gpd

from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML, Contact, Documentation
from owslib.util import testXMLValue, testXMLAttribute, nspath_eval
from owslib.namespaces import Namespaces

from pyoos.collectors.ioos.swe_sos import IoosSweSos
from pyoos.parsers.ioos.describe_sensor import IoosDescribeSensor
from pyoos.parsers.ioos.one.describe_sensor import ont

# from jinja2 import Environment, PackageLoader
# env = Environment(loader=PackageLoader('yourapplication', 'templates'))


class Sensorml2Iso:
    """
    Attributes
    ----------
    service : str
        An IOOS DMAC-compliant SOS service to parse for active sensors to generate metadata for.
    active_station_days : int
        Number of days before present to designate stations as 'active' for inclusion/exclusion purposes.
    more : str
        More class attributes...
    """

    def __init__(self, service=None, active_station_days=None, stations=None, verbose=False):

        self.service = service

        self.active_station_days = active_station_days
        self.stations = stations
        self.verbose = verbose

        self.service_url = urlparse(self.service)
        self.output_directory = self.service_url.netloc

        self.run_test()
        # self.read_config_file()
        # self.load_validation_schema()

    def run(self):
        self.namespaces = self.get_namespaces()
        print("Stations: {stations}".format(stations=self.stations))

        stations_df = self.get_stations_df(self.service, self.stations)

        # Assign EPSG:4326 CRS, retrieved from epsg.io
        # The OGC WKT crs string is available directly at http://epsg.io/4326.wkt
        # or http://spatialreference.org/ref/epsg/4326/ogcwkt/
        crs = '''GEOGCS["WGS 84",
                   DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],
                     AUTHORITY["EPSG","6326"]],
                   PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],
                   UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],
                 AUTHORITY["EPSG","4326"]]'
        '''
        geometry = [Point(xy) for xy in zip(stations_df.lon, stations_df.lat)]
        stations_gdf = gpd.GeoDataFrame(stations_df, geometry=geometry, crs=crs)

        # determine active/inactive:
        station_active_date = datetime.today() - timedelta(days=self.active_station_days)
        active_cnt = len(stations_df[stations_df.ending > station_active_date.isoformat()])
        total_cnt = len(stations_df)
        print("'Active' stations: %d / Total stations: %d" % (active_cnt, total_cnt))

        stations_df[stations_df.ending > station_active_date.isoformat()]
        print(stations_df[stations_df.ending > station_active_date.isoformat()].to_csv())

        return

    # These functions are all from OWSLib, with minor adaptations
    def get_namespaces(self):
        n = Namespaces()
        namespaces = n.get_namespaces(["sml", "gml", "xlink", "swe"])
        namespaces["ism"] = "urn:us:gov:ic:ism:v2"
        return namespaces

    def nsp(self, path):
        return nspath_eval(path, self.namespaces)

    def get_stations_df(self, sos_url, station_urns_sel=None):
        """ Returns a GeoDataFrame
        """
        # LATER: ADD ERROR TEST/CATCH AFTER EACH WEB REQUEST
        oFrmt = 'text/xml; subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"'

        if station_urns_sel is not None:
            params = {'service': 'SOS', 'request': 'GetCapabilities', 'acceptVersions': '1.0.0'}
            sosgc = SensorObservationService(sos_url + '?' + urlencode(params))
            station_urns = station_urns_sel
        else:
            sos_collector = IoosSweSos(sos_url)
            station_urns = [urn.name for urn in sos_collector.server.offerings
                            if 'network' not in urn.name.split(':')]
            sos_collector.features = station_urns
            sml_lst = sos_collector.metadata(timeout=200)

        station_recs = []
        for station_idx, station_urn in enumerate(station_urns):
            if station_urns_sel is not None:
                sml_str = sosgc.describe_sensor(procedure=station_urn, outputFormat=oFrmt,
                                                timeout=200)
                sml = SensorML(sml_str)

            else:
                sml = sml_lst[station_idx]

            # debug MW:
            # text_content approach doesn't work:
            # print(sml._root.text_content)
            if station_idx == 0:
                print(etree.tostring(sml._root))

            ds = IoosDescribeSensor(sml._root)
            # debug MW:
            # print(str(ds))
            if station_idx == 0:
                for var in ds.variables:
                    print(var)

            pos = testXMLValue(ds.system.location.find(self.nsp('gml:Point/gml:pos')))

            system_el = sml._root.findall(self.nsp('sml:member'))[0].find(self.nsp('sml:System'))

            # Assume there's a single DocumentList/member; will read the first one only.
            # Assume that member corresponds to xlink:arcrole="urn:ogc:def:role:webPage"
            documents = system_el.findall(self.nsp('sml:documentation/sml:DocumentList/sml:member'))
            if len(documents) > 0:
                document = Documentation(documents[0])
                webpage_url = document.documents[0].url
            else:
                webpage_url = None

            contacts = system_el.findall(self.nsp('sml:contact/sml:ContactList/sml:member'))
            contacts_dct = {}
            for c in contacts:
                contact = Contact(c)
                role = contact.role.split('/')[-1]
                contacts_dct[role] = contact

            sweQuants = system_el.findall(self.nsp('sml:outputs/sml:OutputList/sml:output/swe:Quantity'))
            quant_lst = [sweQuant.attrib['definition'] for sweQuant in sweQuants]
            parameter_lst = [sweQuant.split('/')[-1] for sweQuant in quant_lst]

            station = OrderedDict()
            station['station_urn'] = station_urn
            station['lon'] = float(pos.split()[1])
            station['lat'] = float(pos.split()[0])

            station['shortName'] = ds.shortName
            station['longName'] = ds.longName
            station['wmoID'] = ds.get_ioos_def('wmoID', 'identifier', ont)

            # Beware that a station can have >1 classifier of the same type
            # This code does not accommodate that possibility
            station['platformType'] = ds.platformType
            station['parentNetwork'] = ds.get_ioos_def('parentNetwork', 'classifier', ont)
            station['sponsor'] = ds.get_ioos_def('sponsor', 'classifier', ont)
            station['webpage_url'] = webpage_url

            station['operatorSector'] = ds.get_ioos_def('operatorSector', 'classifier', ont)
            station['operator_org'] = contacts_dct['operator'].organization
            station['operator_country'] = contacts_dct['operator'].country
            station['operator_url'] = contacts_dct['operator'].url
            # pull out email address(es) too?
            # station_dct['operator_email'] = contacts_dct['operator'].electronicMailAddress

            station['publisher'] = ds.get_ioos_def('publisher', 'classifier', ont)
            station['publisher_org'] = contacts_dct['publisher'].organization
            station['publisher_url'] = contacts_dct['publisher'].url
            # station_dct['publisher_email'] = contacts_dct['publisher'].electronicMailAddress

            station['starting'] = ds.starting
            station['ending'] = ds.ending
            station['starting_isostr'] = datetime.isoformat(ds.starting)
            station['ending_isostr'] = datetime.isoformat(ds.ending)

            station['parameter_uris'] = ','.join(quant_lst)
            station['parameters'] = ','.join(parameter_lst)

            station_recs.append(station)

        stations_df = pd.DataFrame.from_records(station_recs, columns=station.keys())
        stations_df.index = stations_df['station_urn']

        return stations_df

    def run_test(self):
        print("Service: {service}, verbose: {verbose}, o: {o}".format(service=self.service, verbose=self.verbose, o=self.output_directory))
        active_date = datetime.today() - timedelta(days=self.active_station_days)

        print("Date for determining active/inactive stations in SOS service: {active_date}".format(active_date=active_date.strftime("%Y-%m-%d")))
