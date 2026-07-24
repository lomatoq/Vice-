# V-ICE Scene frozen validation campaign

- Freeze: `33bc0d63e4b82734bcb5349f5d19385ac16b0fbdc6e31074814728c90238758f`
- Policy: record-only after freeze; no parameter tuning

| Section | Status | Seconds | Log |
|---|---:|---:|---|
| scene synthetic/build oracle suite | PASS | 11.564 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\01_scene_synthetic_build_oracle_suite.log` |
| synthetic renderer holdout and selector calibration | PASS | 13.72 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\02_synthetic_renderer_holdout_and_selector_calibration.log` |
| regression:test_dp_physical_fidelity | PASS | 0.448 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\03_regression_test_dp_physical_fidelity.log` |
| regression:test_native_density_contract | PASS | 5.477 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\04_regression_test_native_density_contract.log` |
| regression:test_dp4x_contract | PASS | 52.258 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\05_regression_test_dp4x_contract.log` |
| regression:test_digital_circle_court | PASS | 0.784 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\06_regression_test_digital_circle_court.log` |
| regression:test_glyph_repair | PASS | 1.157 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\07_regression_test_glyph_repair.log` |
| regression:test_text_evidence_shield | PASS | 1.074 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\08_regression_test_text_evidence_shield.log` |
| regression:test_stroke_seams | PASS | 1.918 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\09_regression_test_stroke_seams.log` |
| regression:test_structural_diagram_lane | PASS | 1.872 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\10_regression_test_structural_diagram_lane.log` |
| regression:test_jpeg_grid | PASS | 0.494 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\11_regression_test_jpeg_grid.log` |
| regression:test_codec_legitimacy | PASS | 1.049 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\12_regression_test_codec_legitimacy.log` |
| regression:test_eye_metrics | PASS | 3.886 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\13_regression_test_eye_metrics.log` |
| regression:test_strike0_metrics | PASS | 1.201 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\14_regression_test_strike0_metrics.log` |
| current stage regression suite | FAIL | 2082.393 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\15_current_stage_regression_suite.log` |
| VAI50 equal-input external comparison | FAIL | 2761.114 | `benchmarks\scene_validation\33bc0d63e4b82734\logs\16_VAI50_equal-input_external_comparison.log` |
