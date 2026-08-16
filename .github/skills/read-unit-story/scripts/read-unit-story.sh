#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 )); then
    echo "Usage: $0 UNIT [UNIT ...]" >&2
    exit 2
fi

script_dir=$(cd "$(dirname "$0")" && pwd)
wordlist=${WORDLIST_FILE:-"$script_dir/../../../../wordlist.txt"}

if [[ ! -f "$wordlist" ]]; then
    echo "Word list not found: $wordlist" >&2
    exit 1
fi

for unit in "$@"; do
    if [[ ! "$unit" =~ ^[0-9]+$ ]]; then
        echo "Invalid unit number: $unit" >&2
        exit 2
    fi
done

spoken_text=$(
    awk -v requested="$*" '
        BEGIN {
            count = split(requested, units, /[[:space:]]+/)
            for (item = 1; item <= count; item++) {
                wanted[units[item] + 0] = 1
            }
        }
        /^Unit [0-9]+[[:space:]]*$/ {
            unit = $2 + 0
            active = wanted[unit]
            in_story = 0
            if (active) found[unit] = 1
            next
        }
        /^------------------------------------------------------------------------$/ {
            active = 0
            next
        }
        active && !in_story && index($0, " — ") > 0 { next }
        active {
            if (!in_story) {
                if (length(text)) text = text " [[slnc 2000]] "
                text = text $0 " [[slnc 1000]]"
            } else {
                text = text " " $0
            }
            in_story = 1
            story[unit] = 1
        }
        END {
            for (item = 1; item <= count; item++) {
                unit = units[item] + 0
                if (!found[unit]) {
                    print "Unit " unit " not found" > "/dev/stderr"
                    failed = 1
                } else if (!story[unit]) {
                    print "Unit " unit " has no story" > "/dev/stderr"
                    failed = 1
                }
            }
            if (failed) exit 1
            print text
        }
    ' "$wordlist"
)

if [[ "${READ_UNIT_STORY_DRY_RUN:-0}" == "1" ]]; then
    printf '%s\n' "$spoken_text"
elif command -v say >/dev/null 2>&1; then
    say "$spoken_text"
else
    echo "The macOS say command is unavailable." >&2
    exit 1
fi