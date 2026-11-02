$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$image = 'sega-sms-python-tools'

docker build --quiet --tag $image $root | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker run --rm --interactive --volume "${root}:/sega-sms-python" --workdir /sega-sms-python $image @args
exit $LASTEXITCODE
