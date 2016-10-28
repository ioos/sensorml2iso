### sensorml2iso ###

A simple Python module to query an IOOS SOS service for active sensors and
output ISO 19115-2-compliant xml metadata following a template.

#### Usage: ####
```
python setup.py install
sensorml2iso -s http://data.nanoos.org/52nsos/sos/kvp -d 14 --stations=urn:ioos:station:nanoos:apl_nemo,urn:ioos:station:nanoos:apl_npb1ptwells
```
Parameters:

-s | --service : URL of SOS GetCapabilities

-d | --active_station_days : number of days beyond which to consider station 'inactive' and exclude

--stations : comma-separated list of station URNs to filter on
