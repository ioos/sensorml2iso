import os
import errno
import io
import sys
from datetime import datetime, timedelta
from dateutil import parser
import pytz
# import six

try:
    from urllib.parse import unquote, urlencode, urlparse   # Python 3
except ImportError:
    from urllib import unquote, urlencode  # Python 2
    from urlparse import urlparse
from collections import OrderedDict
# from lxml import etree
from requests.exceptions import ConnectionError, ReadTimeout

# import numpy as np
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

from jinja2 import Environment, PackageLoader


class Sensorml2Iso:
    """
    Attributes
    ----------
    service : str
        An IOOS DMAC-compliant SOS service to parse for active sensors to generate metadata for.
    active_station_days : int
        Number of days before present to designate stations as 'active' for inclusion/exclusion purposes.
    stations : str
        List of station URNs to filter by for processing
    getobs_req_hours : int
        Number of hours from last valid station observation time to use in GetObservation request example URLs
    response_formats : str
        List of responseFormat values to include in GetObservation download links
    output_dir : str
        Name of an output directory (relative) to output ISO 19115-2 XML metadata to
    more : str
        More class attributes...
    """

    RESPONSE_FORMAT_TYPE_MAP = {
        'application/json': 'application/json',
        'application/zip; subtype=x-netcdf': 'application/x-netcdf',
        'text/xml; subtype="om/1.0.0"': 'text/xml',
        'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"': 'text/xml'
    }
    RESPONSE_FORMAT_NAME_MAP = {
        'application/json': 'JSON',
        'application/zip; subtype=x-netcdf': 'NetCDF',
        'text/xml; subtype="om/1.0.0"': 'XML (O&M 1.0)',
        'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"': 'XML (IOOS SOS 1.0 Profile)'
    }

    def __init__(self, service=None, active_station_days=None, stations=None, getobs_req_hours=None, response_formats=None, output_dir=None, verbose=False):
        """
        """

        self.service = service

        self.active_station_days = active_station_days
        self.stations = stations
        self.getobs_req_hours = getobs_req_hours
        self.response_formats = response_formats
        self.verbose = verbose

        self.service_url = urlparse(self.service)
        self.server_name = self.service_url.netloc

        self.log = io.open('sensorml2iso.log', mode='wt', encoding='utf-8')

        if output_dir is not None:
            self.output_directory = output_dir
        else:
            self.output_directory = self.service_url.netloc
        self.output_directory = self.output_directory.replace(":", "_")

        if self.verbose:
            self.run_test()
            try:
                # self.csv = io.open('sensorml2iso.csv', mode='wt', encoding='utf-8')
                self.csv = open('sensorml2iso.csv', mode='wt')
            except OSError:
                pass

            if self.stations is not None:
                self.log.write(u"Station URNs to filter by:\n")
                print("Station URNs to filter by:")
                for station in self.stations:
                    self.log.write(u"URN: {station}\n".format(station=station))
                    print("URN: {station}".format(station=station))
        self.create_output_dir()

    def run(self):
        """
        """
        self.namespaces = self.get_namespaces()
        # obtain the stations DataFrame:
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
        self.stations_gdf = gpd.GeoDataFrame(stations_df, geometry=geometry, crs=crs)

        # determine active/inactive stations (--active_station_days parameter if provided) and filter stations_df accordingly:
        if self.active_station_days is not None:
            station_active_date = datetime.now() - timedelta(days=self.active_station_days)
            active_cnt = len(stations_df[stations_df.ending > station_active_date.isoformat()])
            total_cnt = len(stations_df)
            filtered_stations_df = stations_df.loc[stations_df.ending > station_active_date.isoformat()]
            if self.verbose:
                # print("Date for determining active/inactive stations in SOS service: {active_date}".format(active_date=active_date.strftime("%Y-%m-%d")))
                print("Date for determining active/inactive stations in SOS service: {active_date:%Y-%m-%d}".format(active_date=station_active_date))
                print("'Active' stations: %d / Total stations: %d" % (active_cnt, total_cnt))
                print("DataFrame sizes: Original(stations_df): {len_stations_df:2.0f}, Filtered: {len_filtered_stations_df:2.0f}".format(len_stations_df=len(stations_df), len_filtered_stations_df=len(filtered_stations_df)))
                self.log.write(u"Date for determining active/inactive stations in SOS service: {active_date:%Y-%m-%d}".format(active_date=station_active_date))
                self.log.write(u"'Active' stations: %d / Total stations: %d" % (active_cnt, total_cnt))
                self.log.write(u"DataFrame sizes: Original(stations_df): {len_stations_df:2.0f}, Filtered: {len_filtered_stations_df:2.0f}".format(len_stations_df=len(stations_df), len_filtered_stations_df=len(filtered_stations_df)))

            if self.verbose:
                # self.csv.write(unicode(stations_df[stations_df.ending > station_active_date.isoformat()].to_csv(encoding='utf-8')))
                self.csv.write(stations_df[stations_df.ending > station_active_date.isoformat()].to_csv(encoding='utf-8'))

            self.generate_iso(filtered_stations_df)
        else:
            self.generate_iso(stations_df)
        return

    # These functions are all from OWSLib, with minor adaptations
    def get_namespaces(self):
        """
        """
        n = Namespaces()
        namespaces = n.get_namespaces(["sml", "gml", "xlink", "swe"])
        namespaces["ism"] = "urn:us:gov:ic:ism:v2"
        return namespaces

    def nsp(self, path):
        """
        """
        return nspath_eval(path, self.namespaces)

    def get_stations_df(self, sos_url, station_urns_sel=None):
        """ Returns a GeoDataFrame
        """
        # LATER: ADD ERROR TEST/CATCH AFTER EACH WEB REQUEST
        oFrmt = 'text/xml; subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"'
        params = {'service': 'SOS', 'request': 'GetCapabilities', 'acceptVersions': '1.0.0'}
        sos_url_params = sos_url + '?' + urlencode(params)
        sos_url_params_esc = sos_url_params.replace("&", "&amp;")
        # sos_url_params_quoted = quote(sos_url_params,"/=:")
        # sos_url_params_unquoted = unquote(sos_url_params)

        try:
            sosgc = SensorObservationService(sos_url_params)
        except (ConnectionError, ReadTimeout) as e:
            self.log.write(u"Error: unable to connect to SOS service: {url} due to HTTP connection error.\n".format(url=sos_url_params))
            self.log.write(u"HTTP connection error: {err}.\n".format(err=e.message))
            sys.exit("Error: unable to connect to SOS service: {url}. \nUnderlying HTTP connection error: {err}".format(url=sos_url_params, err=e.message))

        if station_urns_sel is not None:
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

            # debug:
            # if self.verbose:
            #    self.log.write(unicode(etree.tostring(sml._root)))

            ds = IoosDescribeSensor(sml._root)

            pos = testXMLValue(ds.system.location.find(self.nsp('gml:Point/gml:pos')))

            system_el = sml._root.findall(self.nsp('sml:member'))[0].find(self.nsp('sml:System'))

            # Parse the DocumentList into a dict storing documents by index value 'name' (may cause index duplication
            # errors but there is not enough information in SensorML for alternatives)
            # Assume that member corresponds to xlink:arcrole="urn:ogc:def:role:webPage"
            documents = system_el.findall(self.nsp('sml:documentation/sml:DocumentList/sml:member'))
            documents_dct = {}
            for d in documents:
                document = Documentation(d)
                name = testXMLAttribute(d, "name")
                # url = document.documents[0].url
                documents_dct[name] = document

            contacts = system_el.findall(self.nsp('sml:contact/sml:ContactList/sml:member'))
            contacts_dct = {}
            for c in contacts:
                contact = Contact(c)
                role = contact.role.split('/')[-1]
                contacts_dct[role] = contact

            sweQuants = system_el.findall(self.nsp('sml:outputs/sml:OutputList/sml:output/swe:Quantity'))
            quant_lst = [sweQuant.attrib['definition'] for sweQuant in sweQuants]
            parameter_lst = [sweQuant.split('/')[-1] for sweQuant in quant_lst]

            # attempt to read beginPosition, if available:
            beginPosition = testXMLValue(system_el.find(self.nsp('sml:validTime/gml:TimePeriod/gml:beginPosition')))
            try:
                begin_service_date = parser.parse(beginPosition)
            except AttributeError as e:
                begin_service_date = None

            station = OrderedDict()
            station['station_urn'] = station_urn
            station['sos_url'] = sos_url_params_esc
            station['lon'] = float(pos.split()[1])
            station['lat'] = float(pos.split()[0])

            station['shortName'] = ds.shortName
            station['longName'] = ds.longName
            station['wmoID'] = ds.get_ioos_def('wmoID', 'identifier', ont)
            station['serverName'] = self.server_name

            # Some capabilities-level metadata:
            station['title'] = sosgc.identification.title
            station['abstract'] = sosgc.identification.abstract
            station['keywords'] = sosgc.identification.keywords
            station['begin_service_date'] = begin_service_date

            # Beware that a station can have >1 classifier of the same type
            # This code does not accommodate that possibility
            station['platformType'] = ds.platformType
            station['parentNetwork'] = ds.get_ioos_def('parentNetwork', 'classifier', ont)
            station['sponsor'] = ds.get_ioos_def('sponsor', 'classifier', ont)

            # store some nested dictionaries in 'station' for appopriate SensorML sources:
            station['contacts_dct'] = contacts_dct
            station['documents_dct'] = documents_dct

            # MW: the 'operator_' and 'publisher_' attributes can be removed bc they are not used
            # in the template code currently in favor of 'contacts_dct'
            # station['operatorSector'] = ds.get_ioos_def('operatorSector', 'classifier', ont)
            # station['operator_org'] = contacts_dct['operator'].organization
            # station['operator_country'] = contacts_dct['operator'].country
            # station['operator_url'] = contacts_dct['operator'].url
            # station['operator_email'] = contacts_dct['operator'].email

            # station['publisher'] = ds.get_ioos_def('publisher', 'classifier', ont)
            # station['publisher_org'] = contacts_dct['publisher'].organization
            # station['publisher_url'] = contacts_dct['publisher'].url
            # station_dct['publisher_email'] = contacts_dct['publisher'].electronicMailAddress

            station['starting'] = ds.starting
            station['ending'] = ds.ending
            # station['starting_isostr'] = datetime.isoformat(ds.starting)
            # station['ending_isostr'] = datetime.isoformat(ds.ending)

            station['parameter_uris'] = ','.join(quant_lst)
            station['parameters'] = ','.join(parameter_lst)
            station['variables'] = [var.split('/')[-1] for var in ds.variables]

            # debug:
            if self.verbose:
                self.log.write(u"\nProcessing station: {station}\n".format(station=station_urn))
                print("\nProcessing station: {station}".format(station=station_urn))
                for var in ds.variables:
                    self.log.write(u"variable: {var}\n".format(var=var))
                    print("variable: {var}".format(var=var))

            # print(sosgc.contents)
            # for id, offering in sosgc.contents.iteritems():
            #    print("sosgc.contents: {item}".format(item=id))

            # parse 'responseFormat' values and populate list:
            # response_formats = sosgc.contents[station_urn].response_formats
            response_formats = []
            for id, sosgc.content in sosgc.contents.items():
                if sosgc.content.name == station_urn:
                    response_formats = sosgc.content.response_formats
            # response_formats = [ sosgc.content.response_formats for id, sosgc.content in sosgc.contents.items() if sosgc.content.name == station_urn ]

            # subset responseFormats (response_formats) for download links matching those passed in --response_formats parameter
            # (or 'application/json,application/zip; subtype=x-netcdf' by default):
            download_formats = [response_format for response_format in response_formats if response_format in self.response_formats]
            station['response_formats'] = response_formats
            station['download_formats'] = download_formats

            if self.verbose:
                for format in response_formats:
                    self.log.write(u"responseFormat: {format}\n".format(format=format))
                    print("responseFormat: {format}".format(format=format))
                for format in download_formats:
                    self.log.write(u"downloadFormats: {format}\n".format(format=format))
                    print("downloadFormats: {format}".format(format=format))

            # calculate event_time using self.getobs_req_hours:
            if ds.starting is not None and ds.ending is not None:
                event_time = "{begin:%Y-%m-%dT%H:%M:%S}/{end:%Y-%m-%dT%H:%M:%S}\n".format(begin=ds.ending - timedelta(hours=self.getobs_req_hours), end=ds.ending)
            else:
                now = datetime.now(pytz.utc)
                then = now - timedelta(hours=self.getobs_req_hours)
                event_time = "{begin:%Y-%m-%dT%H:%M:%S}/{end:%Y-%m-%dT%H:%M:%S}\n".format(begin=then, end=now)
                if self.verbose:
                    self.log.write(u"then: {then:%Y-%m-%dT%H:%M:%S%z}, now: {now:%Y-%m-%dT%H:%M:%S%z}\n".format(then=then, now=now))
                    print("then: {then:%Y-%m-%dT%H:%M:%S%z}, now: {now:%Y-%m-%dT%H:%M:%S%z}".format(then=then, now=now))

            if self.verbose:
                self.log.write(u"eventTime: {time}\n".format(time=event_time))
                print("eventTime: {time}".format(time=event_time))

            # create a dict to store parameters for valid example GetObservation requests for station:
            getobs_req_dct = {}
            # populate a parameters dictionary for download links for each 'observedProperty' type and secondly for each 'responseFormat' per observedProperty:
            getobs_params_base = {'service': 'SOS', 'request': 'GetObservation', 'version': '1.0.0', 'offering': station_urn, 'eventTime': event_time}
            for variable in ds.variables:
                getobs_params = getobs_params_base.copy()
                getobs_params['observedProperty'] = variable
                variable = variable.split('/')[-1]
                for format in download_formats:
                    getobs_params['responseFormat'] = format
                    getobs_request_url_encoded = sos_url + '?' + urlencode(getobs_params)
                    getobs_request_url = unquote(getobs_request_url_encoded)
                    getobs_request_url_esc = getobs_request_url.replace("&", "&amp;")
                    getobs_req_dct[variable + '-' + format] = {
                        'variable': variable,
                        'url': getobs_request_url_esc,
                        'format_type': self.RESPONSE_FORMAT_TYPE_MAP[format],
                        'format_name': self.RESPONSE_FORMAT_NAME_MAP[format]
                    }
                    if self.verbose:
                        self.log.write(u"getobs_request_url (var: {variable}): {getobs_request_url}\ngetobs_request_url_esc (var: {variable}): {getobs_request_url_esc}\n".format(variable=variable.split("/")[-1], getobs_request_url=getobs_request_url, getobs_request_url_esc=getobs_request_url_esc))
                        print("getobs_request_url (var: {variable}): {getobs_request_url}\ngetobs_request_url_esc (var: {variable}): {getobs_request_url_esc}".format(variable=variable.split("/")[-1], getobs_request_url=getobs_request_url, getobs_request_url_esc=getobs_request_url_esc))

            # ToDo: finish adding the 'getobs_req_dct' to the output template
            station['getobs_req_dct'] = getobs_req_dct

            station_recs.append(station)

        stations_df = pd.DataFrame.from_records(station_recs, columns=station.keys())
        stations_df.index = stations_df['station_urn']

        return stations_df

    def generate_iso(self, df):
        """
        """

        # set up the Jinja2 template:
        env = Environment(loader=PackageLoader('sensorml2iso', 'templates'), trim_blocks=True, lstrip_blocks=True)
        # env.filters['sixiteritems'] = six.iteritems
        template = env.get_template('sensorml_iso.xml')

        for idx, station in df.iterrows():
            ctx = {}
            # populate some general elements for the template:
            # we can use format filters in the template to format dates...
            # ctx['metadataDate'] = "{metadata_date:%Y-%m-%d}".format(metadata_date=datetime.today())
            ctx['metadataDate'] = datetime.now()

            # debug: get the first station:
            # station = df.iloc[0]

            ctx['identifier'] = station.station_urn
            ctx['contacts_dct'] = station['contacts_dct']
            ctx['documents_dct'] = station['documents_dct']

            ctx['sos_url'] = station['sos_url']
            ctx['lon'] = station['lon']
            ctx['lat'] = station['lat']
            ctx['shortName'] = station.shortName
            ctx['longName'] = station.longName
            ctx['wmoID'] = station.wmoID
            ctx['serverName'] = station.serverName

            ctx['title'] = station.title
            ctx['abstract'] = station.abstract
            ctx['keywords'] = station.keywords
            ctx['beginServiceDate'] = station.begin_service_date

            ctx['platformType'] = station.platformType
            ctx['parentNetwork'] = station.parentNetwork
            ctx['sponsor'] = station.sponsor

            ctx['starting'] = station.starting
            ctx['ending'] = station.ending

            ctx['parameter_uris'] = station.parameter_uris
            ctx['parameters'] = station.parameter_uris
            ctx['variables'] = station.variables
            ctx['response_formats'] = station.response_formats
            ctx['download_formats'] = station.download_formats
            ctx['getobs_req_dct'] = station.getobs_req_dct

            output_filename = os.path.join(self.output_directory, "{serverName}-{station}.xml".format(serverName=self.server_name, station=station.station_urn.replace(":", "_")))
            try:
                iso_xml = template.render(ctx)
                output_file = io.open(output_filename, mode='wt', encoding='utf8')
                output_file.write(iso_xml)
                output_file.close()
                if self.verbose:
                    self.log.write(u"\nMetadata for station: {station} written to output file: {out_file}\n".format(station=station.station_urn, out_file=os.path.abspath(output_filename)))
                    # self.log.write(iso_xml)
                    print("\nMetadata for station: {station} written to output file: {out_file}".format(station=station.station_urn, out_file=os.path.abspath(output_filename)))
                    # print(iso_xml)
            except OSError as ex:
                if ex.errno == errno.EEXIST:
                    self.log.write(u"Output file: {out_file} already exists, skipping.\n".format(out_file=output_filename))
                    print("Output file: {out_file} already exists, skipping.".format(out_file=output_filename))
                    # sys.exit("Error: the output directory passed: {output_dir} already exists.".format(output_dir=os.path.abspath(self.output_directory)))
                else:
                    sys.exit("Error: Unable to open output file: {out_file} for writing, aborting.".format(out_file=output_filename))

    def create_output_dir(self):
        """
        """
        try:
            os.makedirs(self.output_directory)
            # test error handling:
            # raise OSError
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(self.output_directory):
                self.log.write(u"Error: the configured output directory: {output_dir} already exists.\n".format(output_dir=os.path.abspath(self.output_directory)))
                sys.exit("Error: the configured output directory: {output_dir} already exists.".format(output_dir=os.path.abspath(self.output_directory)))
            else:
                self.log.write(u"Error: the configured output directory: {output_dir} was not able to be created.\n".format(output_dir=os.path.abspath(self.output_directory)))
                sys.exit("Error: the configured output directory: {output_dir} was not able to be created.".format(output_dir=os.path.abspath(self.output_directory)))

    def run_test(self):
        """
        """
        # just print out some parameter info:
        if self.verbose:
            self.log.write(u"sensorml2iso:\n______________\nService: {service}\nStations (--stations): {stations}\nActive Station Days (-d|--active_station_days): {active_station_days}\nGetObs Request Hours (--getobs_req_hours): {getobs_req_hours}\nOutput Dir (--output_dir): {output_dir}\n______________\n\n".format(service=self.service, stations=self.stations, active_station_days=self.active_station_days, getobs_req_hours=self.getobs_req_hours, output_dir=os.path.abspath(self.output_directory)))
            print("sensorml2iso:\n______________\nService: {service}\nStations (--stations): {stations}\nActive Station Days (-d|--active_station_days): {active_station_days}\nGetObs Request Hours (--getobs_req_hours): {getobs_req_hours}\nOutput Dir (--output_dir): {output_dir}\n______________\n\n".format(service=self.service, stations=self.stations, active_station_days=self.active_station_days, getobs_req_hours=self.getobs_req_hours, output_dir=os.path.abspath(self.output_directory)))
