# Official CBDT schemas — AY 2026–27

Unmodified JSON files downloaded from the Income Tax Department on 2026-09-22:

- ITR-1: https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-06/ITR-1_2026_Main_V1.1.json
- ITR-2: https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-08/ITR-2_2026_Main_V1.2.json
- ITR-4: https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-07/ITR-4_2026_Main_V1.1.json

`manifest.json` pins the original bytes using SHA-256. The loader validates the hash and uses the JSON Schema Draft 4 validator. Missing years, corrupt schemas and invalid payloads fail closed. Do not alter schemas to make an application payload pass. Update both the official file and manifest when intentionally adopting a new published version.

The current simplified builders are not yet compatible with every official schedule. Installing schemas does not imply that export is ready or that a schema-valid payload will pass portal business validations.
