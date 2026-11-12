#!/bin/sh
# Finish native acceptance on the lab node after the primary batch closes.
set -eu
umask 077

work=$1
corpus_root=$2
initial_source=$3
current_source=$4
python=$5
recompiled_source=$6
label=$7
tools=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

cd "$work"
trap 'code=$?; printf "%s\n" "$code" > "finish_corpus_$label.EXIT"' EXIT
primary=runs/corpus_5344
retest=runs/retest_$label
recompiled=revalidated_v111
mkdir -p "$retest"
until test -f "$primary/EXIT.json" && test ! -e "$primary/RUNNING" && test ! -e "$retest/RUNNING"; do
    sleep 5
done

"$python" "$tools/select_retests.py" "$recompiled/checks.jsonl" "$primary" \
    "$retest/final_ids.txt" --primary-finished

if test -s "$retest/final_ids.txt"; then
    export DRAWIO_COMPARE_SOURCE="$work/baseline_source/conversion"
    "$python" -u "$current_source/batch.py" "$work/corpus/corpus.jsonl" --root "$corpus_root" \
        --out "$retest" --only "$retest/final_ids.txt" --workers 12 --retry-rejected || test "$?" -eq 1
fi

"$python" -u "$tools/close_corpus.py" corpus/corpus.jsonl "$primary" "$retest" \
    "$initial_source" "$current_source" "closure_$label" --revalidated "$recompiled" \
    --recompiled-with "$recompiled_source"
