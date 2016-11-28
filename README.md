### sensorml2iso ###

A simple Python module to query an IOOS SOS service for active sensors and
output ISO 19115-2-compliant xml metadata following a template.

#### Installation: ####
```
git clone https://github.com/ioos/sensorml2iso.git
cd sensorml2iso
pip install -e .
```

#### Usage: ####
```
sensorml2iso -s http://data.nanoos.org/52nsos/sos/kvp
```

or, with all optional parameters:
```
sensorml2iso -s http://data.nanoos.org/52nsos/sos/kvp -d 14 --stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells
                    --getobs_req_hours 3 --response_formats=application/json,application/zip; subtype=x-netcdf --output_dir data.nanoos.org --verbose
```

Parameters:

-s | --service : SOS service endpoint URL

-d | --active_station_days : (Optional) Number of days from present to use to filter SOS stations not actively reporting observations for active/inactive designation.  Inactive stations are excluded from processing.

--stations : (Optional) Comma-separated list of station URNs to filter by. Eg. '--stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells'.

--getobs_req_hours : (Optional) Number of hours from last valid station observation time to use in GetObservation request example URLs.  Default: 2.

--response_formats : (Optional) Comma-separated list of SOS responseFormats to use in creating GetObservation download links for each observed parameter.  Eg. '--response_formats=application/json,application/zip; subtype=x-netcdf'.  Default: ['application/json', 'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"'].

--output_dir : (Optional) Specify an output directory (relative to current working directory) to write ISO 19115-2 XML files to.  If omitted the default output directory will a subdirectory using the domain name of the SOS service URL passed (eg. sos.gliders.ioos.us).

--verbose : (Optional) verbose output to stdout and log file sensorml2iso.log
