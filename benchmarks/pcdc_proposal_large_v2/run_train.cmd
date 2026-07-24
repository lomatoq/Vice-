@echo off
cd /d "C:\Users\nirrt\Toolset\v-ice part"
C:\Python312\python.exe -m vice_compiler.train_proposal_net_large --checkpoint models\proposal_net_large_candidate_v2.pt --report benchmarks\pcdc_proposal_large_v2\report.json --progress benchmarks\pcdc_proposal_large_v2\progress.json --epochs 8 --batch-size 64 --workers 2 --image-size 128 --hidden-dim 128 --query-count 32 --decoder-layers 3 --parameter-dim 16 --lr 8e-4 --minimum-recall 0.97 --quiet 1>benchmarks\pcdc_proposal_large_v2\train.out.log 2>benchmarks\pcdc_proposal_large_v2\train.err.log
