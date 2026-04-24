# assets/

## bengaluru-wards.geojson  ← REQUIRED

Download Bengaluru ward boundary GeoJSON from:

  https://github.com/datameet/maps/tree/master/districts/bangalore

Place the file here as: assets/bengaluru-wards.geojson

The GeoJSON must have ward properties with one of these field names:
  - ward_no  (preferred)
  - id
  - ward_id

And ward name in one of:
  - ward_name  (preferred)
  - name

If field names differ in your file, update helpers.wardIdFromFeature()
and helpers.wardNameFromFeature() in js/utils/helpers.js.

Without this file the map will show base tiles only (no ward polygons).
The app will still work — risk scores will load and the panel will open
when wards are selected via the search bar.
