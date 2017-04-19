### sensorml2iso ###

A simple Python module to query an IOOS SOS service for active sensors and
output ISO 19115-2-compliant xml metadata following a template.

#### Installation: ####
```
git clone https://github.com/ioos/sensorml2iso.git
cd sensorml2iso
python setup.py install
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

```
-s | --service : SOS service endpoint URL

-d | --active_station_days : (Optional) Number of days from present to use to filter SOS stations
     not actively reporting observations for active/inactive designation.  Inactive stations are
     excluded from processing.

--stations : (Optional) Comma-separated list of station URNs to filter by.
     Eg. '--stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells'.

--getobs_req_hours : (Optional) Number of hours from last valid station observation time to use
     in GetObservation request example URLs.  Default: 2.

--response_formats : (Optional) Comma-separated list of SOS responseFormats to use in creating
     GetObservation download links for each observed parameter.
     Eg. "--response_formats='application/json,application/zip; subtype=x-netcdf'".
     Default: ['application/json', 'text/xml; subtype="om/1.0.0/profiles/ioos_sos/1.0"'].

--output_dir : (Optional) Specify an output directory (relative to current working directory)
     to write ISO 19115-2 XML files to.  If omitted the default output directory will a subdirectory
     using the domain name of the SOS service URL passed (eg. sos.gliders.ioos.us).

--sos_type: (Optional) Identify the type of SOS service to query.  Currently this isn't implemented,
    but could be used to use specific parsers built into the Pyoos library.  Valid types: 'ioos', 'ndbc', 'coops'.

--verbose : (Optional) verbose output to stdout and log file sensorml2iso.log
```


#### Docker

To run the command using docker:

```
docker run -v $PWD/iso:/srv/iso --name sensorml2iso -it --rm ioos/sensorml2iso -s http://sos.glos.us/52n/sos/kvp --output_dir /srv/iso/glos
```

To run the container as a service:

Example config.json:

```json
[
    {
        "service": "http://sdf.ndbc.noaa.gov/sos/server.php",
        "output_dir": "/srv/iso/ndbc",
        "response_formats": [
            "text/csv",
            "text/xml;schema=\"ioos/0.6.1\""
        ],
        "schedule": "0 * * * *"
    },
    {
        "service": "http://opendap.co-ops.nos.noaa.gov/ioos-dif-sos/SOS",
        "output_dir": "/srv/iso/co-ops",
        "response_formats": [
            "text/csv",
            "text/xml;subtype=\"om/1.0.0/profiles/ioos_sos/1.0\""
        ],
        "schedule": "10 * * * *"
    },
    {
        "service": "http://sos.glos.us/52n/sos/kvp",
        "output_dir": "/srv/iso/glos",
        "schedule": "20 * * * *"
    }
]
```

```
docker run --name sensorml2iso -it -v $PWD/config.json:/etc/sensorml2iso/config.json ioos/sensorml2iso
```
