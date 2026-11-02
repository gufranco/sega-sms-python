#!/usr/bin/env bash
set -euo pipefail

version=${1:?version required}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
target="${root}/segasms/version.py"
citation="${root}/CITATION.cff"

if ! grep -q '^VERSION = "' "$target"; then
  printf 'no VERSION assignment found in %s\n' "$target" >&2
  exit 1
fi

if ! grep -q '^version: ' "$citation"; then
  printf 'no version found in %s\n' "$citation" >&2
  exit 1
fi

tmp=$(mktemp "${TMPDIR:-/tmp}/segasms-version-XXXXXX")
sed "s/^VERSION = \".*\"$/VERSION = \"${version}\"/" "$target" >"$tmp"
mv "$tmp" "$target"

tmp=$(mktemp "${TMPDIR:-/tmp}/segasms-citation-XXXXXX")
sed "s/^version: .*$/version: ${version}/" "$citation" >"$tmp"
mv "$tmp" "$citation"

written=$(grep '^VERSION = ' "$target" | cut -d'"' -f2)
cited=$(sed -n 's/^version: \(.*\)$/\1/p' "$citation")

if [[ ${written} != "${version}" ]]; then
  printf 'wanted %s in %s, found %s\n' "$version" "$target" "$written" >&2
  exit 1
fi

if [[ ${cited} != "${version}" ]]; then
  printf 'wanted %s in %s, found %s\n' "$version" "$citation" "$cited" >&2
  exit 1
fi

printf 'version set to %s\n' "$written"
