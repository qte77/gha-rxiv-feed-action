#!/usr/bin/env bash
# Render a papers-per-ISO-week bar chart SVG from <data_dir>/<year>/<week>.csv.
#
# Usage: weekly_svg.sh DATA_DIR [OUT_FILE] [WEEKS]
#   OUT_FILE defaults to DATA_DIR/weekly.svg; WEEKS (default 26) caps the
#   chart to the most recent N weeks.
#
# Counts CSV records, not lines: a quoted cell with an embedded newline
# stays one record. Output is deterministic (no timestamps), so an unchanged
# data dir yields a byte-identical SVG and no spurious data PR. Colors follow
# prefers-color-scheme, so GitHub renders it in light or dark to match.
set -euo pipefail

data_dir="${1:?usage: weekly_svg.sh DATA_DIR [OUT_FILE] [WEEKS]}"
out_file="${2:-$data_dir/weekly.svg}"
weeks="${3:-26}"
name="$(basename "$data_dir")"

shopt -s nullglob
files=("$data_dir"/[0-9]*/[0-9]*.csv)

count_weeks() {
  [ "${#files[@]}" -eq 0 ] && return 0
  # A record ends on a line where the running count of '"' is even.
  awk '
    FNR == 1 {
      n = split(FILENAME, parts, "/")
      week = parts[n]; sub(/\.csv$/, "", week)
      key = parts[n - 1] " " week
      recs[key] = -1  # the header record
      q = 0
    }
    {
      q += gsub(/"/, "&")
      if (q % 2 == 0) { recs[key]++; q = 0 }
    }
    END { for (k in recs) print k, recs[k] }
  ' "${files[@]}"
}

count_weeks | sort -n -k1,1 -k2,2 | tail -n "$weeks" | awk -v name="$name" '
  { year[NR] = $1; week[NR] = $2; count[NR] = $3; if ($3 > max) max = $3 }
  END {
    w = 720; h = 240; left = 48; right = 16; top = 36; bottom = 32
    pw = w - left - right; ph = h - top - bottom
    printf "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" viewBox=\"0 0 %d %d\" role=\"img\">\n", w, h, w, h
    printf "<title>%s: papers per ISO week</title>\n", name
    print "<style>"
    print "  .bg { fill: #ffffff; } .bar { fill: #2a78d6; } .axis { stroke: #d0d7de; }"
    print "  .txt { fill: #1f2328; font: 12px -apple-system, Segoe UI, Helvetica, Arial, sans-serif; }"
    print "  .muted { fill: #59636e; }"
    print "  @media (prefers-color-scheme: dark) {"
    print "    .bg { fill: #0d1117; } .bar { fill: #3987e5; } .axis { stroke: #30363d; }"
    print "    .txt { fill: #f0f6fc; } .muted { fill: #9198a1; }"
    print "  }"
    print "</style>"
    printf "<rect class=\"bg\" width=\"%d\" height=\"%d\"/>\n", w, h
    printf "<text class=\"txt\" x=\"%d\" y=\"22\">%s: papers per ISO week</text>\n", left, name
    printf "<line class=\"axis\" x1=\"%d\" y1=\"%d\" x2=\"%d\" y2=\"%d\"/>\n", left, top + ph, left + pw, top + ph
    if (NR == 0) {
      printf "<text class=\"txt muted\" x=\"%d\" y=\"%d\" text-anchor=\"middle\">No data yet</text>\n", w / 2, top + ph / 2
      print "</svg>"
      exit
    }
    if (max == 0) max = 1
    printf "<text class=\"txt muted\" x=\"%d\" y=\"%d\" text-anchor=\"end\">%d</text>\n", left - 6, top + 4, max
    printf "<text class=\"txt muted\" x=\"%d\" y=\"%d\" text-anchor=\"end\">0</text>\n", left - 6, top + ph + 4
    slot = pw / NR; gap = (slot > 6) ? 2 : 0
    for (i = 1; i <= NR; i++) {
      bh = count[i] / max * ph
      x = left + (i - 1) * slot + gap / 2
      label = sprintf("%s-W%02d", year[i], week[i])
      printf "<rect class=\"bar\" x=\"%.1f\" y=\"%.1f\" width=\"%.1f\" height=\"%.1f\"><title>%s: %d papers</title></rect>\n", x, top + ph - bh, slot - gap, bh, label, count[i]
    }
    first = sprintf("%s-W%02d", year[1], week[1])
    last = sprintf("%s-W%02d", year[NR], week[NR])
    printf "<text class=\"txt muted\" x=\"%d\" y=\"%d\">%s</text>\n", left, h - 10, first
    printf "<text class=\"txt muted\" x=\"%d\" y=\"%d\" text-anchor=\"end\">%s</text>\n", left + pw, h - 10, last
    print "</svg>"
  }
' > "$out_file"
