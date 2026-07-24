//! Dependency-free native kernels for the PCDC runtime hot path.

use std::slice;

const VERSION: u32 = 1;

#[no_mangle]
pub extern "C" fn pcdc_native_version() -> u32 {
    VERSION
}

/// Build symmetric candidate-conflict bitsets from packed support bitsets.
/// Both matrices are row-major arrays of u64 words; diagonal bits stay clear.
#[no_mangle]
pub unsafe extern "C" fn pcdc_conflict_masks(
    support: *const u64,
    rows: usize,
    support_words: usize,
    output: *mut u64,
    output_words: usize,
) -> i32 {
    if support.is_null() || output.is_null() || rows == 0 || support_words == 0 {
        return -1;
    }
    if output_words < (rows + 63) / 64 {
        return -2;
    }
    let input = slice::from_raw_parts(support, rows * support_words);
    let result = slice::from_raw_parts_mut(output, rows * output_words);
    result.fill(0);
    for first in 0..rows {
        for second in (first + 1)..rows {
            let mut overlaps = false;
            for word in 0..support_words {
                if input[first * support_words + word]
                    & input[second * support_words + word] != 0
                {
                    overlaps = true;
                    break;
                }
            }
            if overlaps {
                result[first * output_words + second / 64] |= 1u64 << (second % 64);
                result[second * output_words + first / 64] |= 1u64 << (first % 64);
            }
        }
    }
    0
}

/// Signed distance to a circle for a packed xy point array.
#[no_mangle]
pub unsafe extern "C" fn pcdc_circle_sdf(
    xy: *const f64,
    count: usize,
    cx: f64,
    cy: f64,
    radius: f64,
    output: *mut f64,
) -> i32 {
    if xy.is_null() || output.is_null() || !radius.is_finite() || radius < 0.0 {
        return -1;
    }
    let points = slice::from_raw_parts(xy, count * 2);
    let result = slice::from_raw_parts_mut(output, count);
    for index in 0..count {
        let dx = points[index * 2] - cx;
        let dy = points[index * 2 + 1] - cy;
        result[index] = (dx * dx + dy * dy).sqrt() - radius;
    }
    0
}

/// Deterministic shelf packing used by the exact ROI atlas.
/// `wh` and `xyxy` are row-major [width,height] and [x1,y1,x2,y2].
#[no_mangle]
pub unsafe extern "C" fn pcdc_pack_atlas(
    wh: *const u32,
    count: usize,
    target_width: u32,
    padding: u32,
    xyxy: *mut u32,
    atlas_wh: *mut u32,
) -> i32 {
    if wh.is_null() || xyxy.is_null() || atlas_wh.is_null() || count == 0 {
        return -1;
    }
    let sizes = slice::from_raw_parts(wh, count * 2);
    let placements = slice::from_raw_parts_mut(xyxy, count * 4);
    let atlas = slice::from_raw_parts_mut(atlas_wh, 2);
    let mut x = 0u32;
    let mut y = 0u32;
    let mut row_height = 0u32;
    let mut atlas_width = 0u32;
    for index in 0..count {
        let width = sizes[index * 2];
        let height = sizes[index * 2 + 1];
        if x > 0 && x.saturating_add(width) > target_width {
            x = 0;
            y = y.saturating_add(row_height).saturating_add(padding);
            row_height = 0;
        }
        placements[index * 4] = x;
        placements[index * 4 + 1] = y;
        placements[index * 4 + 2] = x.saturating_add(width);
        placements[index * 4 + 3] = y.saturating_add(height);
        atlas_width = atlas_width.max(x.saturating_add(width));
        x = x.saturating_add(width).saturating_add(padding);
        row_height = row_height.max(height);
    }
    atlas[0] = atlas_width;
    atlas[1] = y.saturating_add(row_height);
    0
}
