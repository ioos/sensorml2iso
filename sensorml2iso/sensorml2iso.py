import os
import errno
import io
import sys
from datetime import datetime, timedelta
from dateutil import parser
import pytz
from six import iteritems

try:
    from urllib.parse import unquote, unquote_plus, urlencode, urlparse   # Python 3
except ImportError:
    from urllib import unquote, unquote_plus, urlencode  # Python 2
    from urlparse import urlparse
from collections import OrderedDict
from lxml import etree
from requests.exceptions import ConnectionError, ReadTimeout

# import numpy as np
import pandas as pd
# from shapely.geometry import Point
# import geopandas as gpd

from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML, Contact, Documentation
from owslib.util import testXMLValue, testXMLAttribute, nspath_eval, ServiceException
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
    sos_type : str
        Name of SOS implementation type [ioos|ndbc|coops]
    output_dir : str
        Name of an output directory (relative) to output ISO 19115-2 XML metadata to
    more : str
        More class attributes...
    """

    RESPONSE_FORMAT_TYPE_MAP = {
        'application/json': 'application/json',
        'application/zip; subtype=x-netcdf': 'application/x-netcdf',
        'text/xml; subtype="om/1.0.0"': 'text/xml',
        'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"': 'text/xml',
        'text/xml;schema="ioos/0.6.1"': 'text/xml',
        'application/ioos+xml;version=0.6.1': 'text/xml'
    }
    RESPONSE_FORMAT_NAME_MAP = {
        'application/json': 'JSON',
        'application/zip; subtype=x-netcdf': 'NetCDF',
        'text/xml; subtype="om/1.0.0"': 'XML (O&M 1.0)',
        'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"': 'XML (IOOS SOS 1.0 Profile)',
        'text/csv': 'CSV',
        'text/tab-separated-values': 'CSV (Tab Separated)',
        'text/xml;schema="ioos/0.6.1"': 'XML',
        'application/ioos+xml;version=0.6.1': 'XML'
    }

    def __init__(self, service=None, active_station_days=None, stations=None, getobs_req_hours=None, response_formats=None, sos_type=None, output_dir=None, verbose=False):
        """
        """

        self.service = service

        self.active_station_days = active_station_days
        self.stations = stations
        self.getobs_req_hours = getobs_req_hours
        self.response_formats = response_formats
        self.sos_type = sos_type
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
            self.print_debug_info()
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

        if os.path.exists(self.output_directory):
            if not os.path.isdir(self.output_directory):
                self.log.write(u"\nError: the configured output directory: {output_dir} exists, but is not a directory".format(output_dir=os.path.abspath(self.output_directory)))
                sys.exit("Error: the configured output directory: {output_dir} exists, but is not a directory".format(output_dir=os.path.abspath(self.output_directory)))
        else:
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
        # crs = '''GEOGCS["WGS 84",
        #           DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],
        #             AUTHORITY["EPSG","6326"]],
        #           PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],
        #           UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],
        #         AUTHORITY["EPSG","4326"]]'
        # '''
        # geometry = [Point(xy) for xy in zip(stations_df.lon, stations_df.lat)]
        # self.stations_gdf = gpd.GeoDataFrame(stations_df, geometry=geometry, crs=crs)

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
        """ Returns a Pandas Dataframe
        """
        # oFrmts: IOOS SOS OutputFormat strings (first is compliant to the IOOS SOS spec, second is to accommodate NDBC).  More info here:
        # http://ioos.github.io/sos-guidelines/doc/wsdd/sos_wsdd_github_notoc/#describesensor-request:638e0b263020c13a76a55332bd966dbe
        oFrmts = ['text/xml; subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"', 'text/xml;subtype="sensorML/1.0.1"']
        params = {'service': 'SOS', 'request': 'GetCapabilities', 'acceptVersions': '1.0.0'}
        sos_url_params = sos_url + '?' + urlencode(params)
        sos_url_params_esc = sos_url_params.replace("&", "&amp;")
        # sos_url_params_quoted = quote(sos_url_params,"/=:")
        # sos_url_params_unquoted = unquote(sos_url_params)

        try:
            sosgc = SensorObservationService(sos_url_params)
        except (ConnectionError, ReadTimeout) as e:
            self.log.write(u"Error: unable to connect to SOS service: {url} due to HTTP connection error.\n".format(url=sos_url_params))
            self.log.write(u"HTTP connection error: {err}.\n".format(err=str(e)))
            sys.exit("Error: unable to connect to SOS service: {url}. \nUnderlying HTTP connection error: {err}\n".format(url=sos_url_params, err=str(e)))

        # vars to store returns from sos_collector.metadata_plus_exceptions function:
        sml_recs = {}
        sml_errors = {}
        describe_sensor_url = {}

        # leverage Pyoos Collector to query for all available stations and obtain SensorML (if station subset not passed in --stations param)
        if station_urns_sel is not None:
            station_urns = station_urns_sel
        else:
            sos_collector = IoosSweSos(sos_url)
            station_urns = [urn.name for urn in sos_collector.server.offerings
                            if 'network' not in urn.name.split(':')]
            sos_collector.features = station_urns

            # write out stations in SOS that will be handled:
            if self.verbose:
                self.log.write(u"\nStations to process for SOS: {sos}".format(sos=sos_url_params))
                print("Stations to process for SOS: {sos}".format(sos=sos_url_params))
                for feature in sos_collector.features:
                    self.log.write(u"\n - {feature}".format(feature=feature))
                    print(" - {feature}".format(feature=feature))

            # iterate over possible oFrmts expected of the various SOS services (IOOS SOS 1.0, NDBC):
            # for fmt in reversed(oFrmts):
            for fmt in oFrmts:
                try:
                    sml_recs, sml_errors = sos_collector.metadata_plus_exceptions(output_format=fmt, timeout=200)
                    # if no valid SensorML docs returned, try next oFrmt:
                    if not sml_recs:
                        continue
                    else:
                        # assign correct DescribeSensor url (use sos_collector.feature rather than sml_recs.keys() to
                        # create DescribeSensor URLs for failures to record in logs):
                        for station in sos_collector.features:
                            describe_sensor_url[station] = self.generate_describe_sensor_url(sosgc, procedure=station, oFrmt=fmt)

                        # report on errors returned from metadata_plus_exceptions:
                        if sml_errors:
                            if self.verbose:
                                for station, msg in iteritems(sml_errors):
                                    self.log.write(u"\nSOS DescribeSensor error returned for: {station}, skipping. Error msg: {msg}".format(station=station, msg=msg))
                                    print("SOS DescribeSensor error returned for: {station}, skipping. Error msg: {msg}".format(station=station, msg=msg))
                        else:
                            self.log.write(u"\nSuccess, no errors returned from DescribeSensor requests in service: {sos}".format(sos=sos_url_params))
                            print("Success, no errors returned from DescribeSensor requests in service: {sos}".format(sos=sos_url_params))
                    break
                # ServiceException shouldn't be thrown by metadata_plus_exceptions function, but handle regardless by attempting next oFrmt:
                except ServiceException as e:
                    continue

        station_recs = []
        failures = []
        # generate Pandas DataFrame by populating 'station_recs' list by parsing SensorML strings:
        for station_idx, station_urn in enumerate(station_urns):
            if station_urns_sel is not None:
                # iterate oFrmts items for describe_sensor request (first is IOOS SOS spec-compliant, second is for NDBC SOS):
                for fmt in oFrmts:
                    try:
                        describe_sensor_url[station_urn] = self.generate_describe_sensor_url(sosgc, procedure=station_urn, oFrmt=fmt)
                        sml_str = sosgc.describe_sensor(procedure=station_urn, outputFormat=fmt, timeout=200)
                        break
                    except ServiceException as e:
                        sml_errors[station_urn] = str(e)
                        continue
                sml = SensorML(sml_str)

            else:
                # process valid SensorML responses, quietly pass on invalid stations (add to failures list for verbose reporting):
                try:
                    sml = sml_recs[station_urn]
                except KeyError:
                    self.log.write(u"\n\nStation: {station} failed (no SensorML in sml_recs dict).  URL: {ds}".format(station=station_urn, ds=describe_sensor_url[station_urn].replace("&amp;", "&")))
                    print("Station: {station} failed (no SensorML in sml_recs dict).  URL: {ds}".format(station=station_urn, ds=describe_sensor_url[station_urn].replace("&amp;", "&")))
                    failures.append(station_urn)
                    continue

            try:
                ds = IoosDescribeSensor(sml._root)
            except AttributeError:
                self.log.write(u"\nInvalid SensorML passed to IoosDescribeSensor.  Check DescribeSensor request for : {station}, URL: ".format(station=station, ds=describe_sensor_url[station_urn].replace("&amp;", "&")))
                print("Invalid SensorML passed to IoosDescribeSensor.  Check DescribeSensor request for : {station}, URL: ".format(station=station, ds=describe_sensor_url[station_urn].replace("&amp;", "&")))

            station = OrderedDict()
            # debug:
            if self.verbose:
                self.log.write(u"\n\nProcessing station: {station}".format(station=station_urn))
                print("Processing station: {station}".format(station=station_urn))
                self.log.write("\n" + etree.tostring(sml._root).decode('utf-8'))

            # assign 'pos' to GML point location (accommodate 'gml:coordinates' as used by NDBC if gml:Point not found):
            try:
                pos = testXMLValue(ds.system.location.find(self.nsp('gml:Point/gml:pos'))) if testXMLValue(ds.system.location.find(self.nsp('gml:Point/gml:pos'))) is not None else testXMLValue(ds.system.location.find(self.nsp('gml:Point/gml:coordinates')))
                station['lon'] = float(pos.split()[1])
                station['lat'] = float(pos.split()[0])
            except AttributeError as e:
                station['lon'] = None
                station['lat'] = None

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

            # obtain list of contacts (accommodate 'sml:contact' element repetition used by NDBC insead of  ContactList):
            contacts = system_el.findall(self.nsp('sml:contact/sml:ContactList/sml:member')) if system_el.findall(self.nsp('sml:contact/sml:ContactList/sml:member')) else system_el.findall(self.nsp('sml:contact'))
            contacts_dct = {}
            for c in contacts:
                contact = Contact(c)
                role = contact.role.split('/')[-1]
                contacts_dct[role] = contact

            sweQuants = system_el.findall(self.nsp('sml:outputs/sml:OutputList/sml:output/swe:Quantity'))
            quant_lst = [sweQuant.attrib['definition'] for sweQuant in sweQuants]
            parameter_lst = [sweQuant.split('/')[-1] for sweQuant in quant_lst]

            # attempt to read beginPosition, if available, otherwise use current date bc ISO requires date value in output location
            # in template:
            beginPosition = testXMLValue(system_el.find(self.nsp('sml:validTime/gml:TimePeriod/gml:beginPosition')))
            try:
                begin_service_date = parser.parse(beginPosition)
            except (AttributeError, TypeError) as e:
                begin_service_date = datetime.now(pytz.utc)

            station['station_urn'] = station_urn
            station['sos_url'] = sos_url_params_esc
            station['describesensor_url'] = describe_sensor_url[station_urn]

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

            station['starting'] = ds.starting
            station['ending'] = ds.ending
            # station['starting_isostr'] = datetime.isoformat(ds.starting)
            # station['ending_isostr'] = datetime.isoformat(ds.ending)

            station['parameter_uris'] = ','.join(quant_lst)
            station['parameters'] = ','.join(parameter_lst)
            station['variables'] = [var.split('/')[-1] for var in ds.variables]

            if self.verbose:
                for var in ds.variables:
                    self.log.write(u"\nvariable: {var}".format(var=var))
                    print("variable: {var}".format(var=var))

            # print(sosgc.contents)
            # for id, offering in sosgc.contents.iteritems():
            #    print("sosgc.contents: {item}".format(item=id))

            # parse 'responseFormat' vals from SensorML:
            # response_formats = sosgc.contents[station_urn].response_formats
            response_formats = []
            for id, sosgc.content in sosgc.contents.items():
                if sosgc.content.name == station_urn:
                    response_formats = sosgc.content.response_formats
            # response_formats = [ sosgc.content.response_formats for id, sosgc.content in sosgc.contents.items() if sosgc.content.name == station_urn ]

            # match responseFormats from SensorML (response_formats) against those passed in --response_formats parameter to
            # populate 'download_formats' list, that is then used to generate GetObservation requests for the template:
            # (default --response_formats values are: 'application/json,application/zip; subtype=x-netcdf' )
            download_formats = [response_format for response_format in response_formats if response_format in self.response_formats]
            station['response_formats'] = response_formats
            station['download_formats'] = download_formats

            if self.verbose:
                for format in response_formats:
                    self.log.write(u"\nresponseFormat: {format}".format(format=format))
                    print("responseFormat: {format}".format(format=format))
                for format in download_formats:
                    self.log.write(u"\ndownloadFormats: {format}".format(format=format))
                    print("downloadFormats: {format}".format(format=format))

            # calculate event_time using self.getobs_req_hours:
            if ds.starting is not None and ds.ending is not None:
                event_time = "{begin:%Y-%m-%dT%H:%M:%S}/{end:%Y-%m-%dT%H:%M:%S}".format(begin=ds.ending - timedelta(hours=self.getobs_req_hours), end=ds.ending)
                if self.verbose:
                    self.log.write(u"\nUsing starting/ending times from SensorML for eventTime")
                    print("Using starting/ending times from SensorML for eventTime")
                    self.log.write(u"\nobservationTimeRange: starting: {start}, ending: {end}".format(start=ds.starting, end=ds.ending))
                    print("observationTimeRange: starting: {start}, ending: {end}".format(start=ds.starting, end=ds.ending))

            else:
                now = datetime.now(pytz.utc)
                then = now - timedelta(hours=self.getobs_req_hours)
                event_time = "{begin:%Y-%m-%dT%H:%M:%S}/{end:%Y-%m-%dT%H:%M:%S}".format(begin=then, end=now)
                if self.verbose:
                    self.log.write(u"\nNo 'observationTimeRange' present in SensorML.  Using present time for eventTime: then: {then:%Y-%m-%dT%H:%M:%S%z}, now: {now:%Y-%m-%dT%H:%M:%S%z}".format(then=then, now=now))
                    print("No 'observationTimeRange' present in SensorML.  Using present time for eventTime: then: {then:%Y-%m-%dT%H:%M:%S%z}, now: {now:%Y-%m-%dT%H:%M:%S%z}".format(then=then, now=now))

            if self.verbose:
                self.log.write(u"\neventTime: {time}".format(time=event_time))
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
                        'format_type': self.RESPONSE_FORMAT_TYPE_MAP.get(format, format),
                        'format_name': self.RESPONSE_FORMAT_NAME_MAP.get(format, format)
                    }
                    if self.verbose:
                        self.log.write(u"\ngetobs_request_url (var: {variable}): {getobs_request_url}\ngetobs_request_url_esc (var: {variable}): {getobs_request_url_esc}".format(variable=variable.split("/")[-1], getobs_request_url=getobs_request_url, getobs_request_url_esc=getobs_request_url_esc))
                        print("getobs_request_url (var: {variable}): {getobs_request_url}\ngetobs_request_url_esc (var: {variable}): {getobs_request_url_esc}".format(variable=variable.split("/")[-1], getobs_request_url=getobs_request_url, getobs_request_url_esc=getobs_request_url_esc))

            # ToDo: finish adding the 'getobs_req_dct' to the output template
            station['getobs_req_dct'] = getobs_req_dct

            station_recs.append(station)

        # extra debug for failed stations in verbose mode:
        if self.verbose:
            self.log.write(u"\n\n\nSOS DescribeSensor request errors recap.  Failed requests:")
            print("SOS DescribeSensor request errors recap.  Failed requests:")
            for station_fail, msg in iteritems(sml_errors):
                self.log.write(u"\n{station} - {msg}.  DescribeSensor URL: {ds}".format(station=station_fail, msg=msg, ds=describe_sensor_url[station_fail].replace("&amp;", "&")))
                print("{station} - {msg}.  DescribeSensor URL: {ds}".format(station=station_fail, msg=msg, ds=describe_sensor_url[station_fail].replace("&amp;", "&")))
            if failures:
                self.log.write(u"\nStations in 'failures' list (should match DescribeSensor errors):")
                print("Stations in 'failures' list (should match DescribeSensor errors):")
                for station_fail in failures:
                    self.log.write(u"\n{station}".format(station=station_fail))
                    print("{station}".format(station=station_fail))

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
            ctx['describesensor_url'] = station['describesensor_url']

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
                    self.log.write(u"\n\nMetadata for station: {station} written to output file: {out_file}".format(station=station.station_urn, out_file=os.path.abspath(output_filename)))
                    print("\nMetadata for station: {station} written to output file: {out_file}".format(station=station.station_urn, out_file=os.path.abspath(output_filename)))
            except OSError as ex:
                if ex.errno == errno.EEXIST:
                    if self.verbose:
                        self.log.write(u"\nWarning, output file: {out_file} already exists, and can't be written to, skipping.".format(out_file=output_filename))
                        print("Warning, output file: {out_file} already exists, and can't be written to, skipping.".format(out_file=output_filename))
                else:
                    self.log.write(u"\Warning: Unable to open output file: {out_file} for writing, skipping.".format(out_file=output_filename))
                    print("Warning: Unable to open output file: {out_file} for writing, skipping.".format(out_file=output_filename))
                    continue

    def generate_describe_sensor_url(self, sos, procedure=None, oFrmt=None):
        """
        """
        # generate a DescribeSensor request to include in the ISO output (lifted from OWSlib):
        try:
            base_url = next((m.get('url') for m in sos.getOperationByName('DescribeSensor').methods if m.get('type').lower() == "get"))
        except StopIteration:
            base_url = sos.url

        if not base_url.endswith("?"):
                base_url = base_url + "?"
        params = {'service': 'SOS', 'version': sos.version, 'request': 'DescribeSensor', 'procedure': procedure, 'outputFormat': oFrmt}
        return base_url + unquote_plus(urlencode(params)).replace("&", "&amp;")

    def create_output_dir(self):
        """
        """
        try:
            os.makedirs(self.output_directory)
            # test error handling:
            # raise OSError
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(self.output_directory):
                self.log.write(u"\nWarning: the configured output directory: {output_dir} already exists. Files will be overwritten.".format(output_dir=os.path.abspath(self.output_directory)))
                print("Warning: the configured output directory: {output_dir} already exists. Files will be overwritten.".format(output_dir=os.path.abspath(self.output_directory)))
                # sys.exit("Error: the configured output directory: {output_dir} already exists.".format(output_dir=os.path.abspath(self.output_directory)))
            else:
                self.log.write(u"\nError: the configured output directory: {output_dir} was not able to be created.".format(output_dir=os.path.abspath(self.output_directory)))
                sys.exit("Error: the configured output directory: {output_dir} was not able to be created.".format(output_dir=os.path.abspath(self.output_directory)))

    def print_debug_info(self):
        """
        """
        # just print out some parameter info:
        if self.verbose:
            self.log.write(u"sensorml2iso:\n______________\nService: {service}\nStations (--stations): {stations}\nActive Station Days (-d|--active_station_days): {active_station_days}\nGetObs Request Hours (--getobs_req_hours): {getobs_req_hours}\nResponse Formats (--response_formats): {response_formats}\nSOS Type (--sos_type): {sos_type}\nOutput Dir (--output_dir): {output_dir}\n______________\n\n".format(service=self.service, stations=self.stations, active_station_days=self.active_station_days, getobs_req_hours=self.getobs_req_hours, response_formats=self.response_formats, sos_type=self.sos_type, output_dir=os.path.abspath(self.output_directory)))
            print("sensorml2iso:\n______________\nService: {service}\nStations (--stations): {stations}\nActive Station Days (-d|--active_station_days): {active_station_days}\nGetObs Request Hours (--getobs_req_hours): {getobs_req_hours}\nResponse Formats (--response_formats): {response_formats}\nSOS Type (--sos_type): {sos_type}\nOutput Dir (--output_dir): {output_dir}\n______________\n\n".format(service=self.service, stations=self.stations, active_station_days=self.active_station_days, getobs_req_hours=self.getobs_req_hours, response_formats=self.response_formats, sos_type=self.sos_type, output_dir=os.path.abspath(self.output_directory)))
