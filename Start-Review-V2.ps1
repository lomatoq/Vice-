# Serve the v2 review queue (append-only expansion corpus) on port 8878.
# The v1 server on 8877 is untouched. Rebuild the queue with:
#   C:\Python312\python.exe build_locus_corpus_v2.py
$env:V_ICE_LOCUS_CORPUS = Join-Path $PSScriptRoot "datasets\pcdc_real_loci_v2"
& C:\Python312\python.exe -u (Join-Path $PSScriptRoot "web_preview\server.py") --port 8878
