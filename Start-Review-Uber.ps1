# Serve the UBER-dataset verification queue (v3) on port 8878 - the
# supervision review the user actually does: local + brand/logo iconify
# records rendered clean at h160, owned SVG bound as source_asset.
# Rebuild/grow the queue with:
#   C:\Python312\python.exe build_locus_corpus_v3_uber.py [--all-iconify]
$env:V_ICE_LOCUS_CORPUS = Join-Path $PSScriptRoot "datasets\pcdc_uber_verify_v3"
& C:\Python312\python.exe -u (Join-Path $PSScriptRoot "web_preview\server.py") --port 8878
