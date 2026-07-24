# V-ICE exact-font bank

Place licensed `.ttf`, `.otf`, or `.ttc` files anywhere below this directory.
The exact-font lane discovers family subdirectories recursively when the
service starts. A font is only allowed to change output after OCR retrieval,
topology, silhouette, boundary, and rendered-pixel proof gates pass.

Large external font banks do not have to be copied into the repository. Set
`VICE_FONT_DIRS` to one or more directories separated by the platform path
separator (`;` on Windows). These files become build inputs and are included
in the build freeze; keep their licenses and exact bytes with a release.

## Clean-room training bank

`google-fonts/` is a sparse checkout of the official Google Fonts repository,
restricted to 81 deliberately varied families.  It currently contains 241
font binaries.  `google-fonts-manifest.json` binds every font and adjacent
license file by SHA-256, records the upstream revision, and permits only the
OFL 1.1 or Ubuntu Font License collections.  Rebuild/verify it with:

```powershell
python -m vice_compiler.font_license_manifest fonts\google-fonts fonts\google-fonts-manifest.json
```

The manifest is a prerequisite for Data Factory v2; discovering an arbitrary
system font directory is not accepted as clean-room provenance.
