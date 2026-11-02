$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$members = @(
    $root,
    (Join-Path $root 'zilog-z80-python'),
    (Join-Path $root 'sega-vdp-python'),
    (Join-Path $root 'sega-vdp-python/ti-tms9918-python'),
    (Join-Path $root 'sega-vdp-python/ti-sn76489-python'),
    (Join-Path $root 'sms-mapper-python')
)

$env:PYTHONPATH = $members -join [IO.Path]::PathSeparator
$env:PYGAME_HIDE_SUPPORT_PROMPT = '1'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA 'sega-sms-python/play'

uv run --project $root --locked --only-group play --python 3.12.14 python -m window.play @args
exit $LASTEXITCODE
