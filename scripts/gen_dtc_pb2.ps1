param(
  [string]$ProtoFile = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$adapterDir = Join-Path $root "sierraflow\adapter"

if ([string]::IsNullOrWhiteSpace($ProtoFile)) {
  $candidate1 = Join-Path $root "DTCProtocol.proto"
  $candidate2 = Join-Path $adapterDir "DTCProtocol.proto"
  if (Test-Path $candidate1) { $ProtoFile = $candidate1 }
  elseif (Test-Path $candidate2) { $ProtoFile = $candidate2 }
  else { throw "DTCProtocol.proto not found. Place it at repo root or sierraflow/adapter/." }
}

$protoDir = Split-Path -Parent $ProtoFile

Write-Host "[gen_dtc_pb2] Using proto: $ProtoFile" -ForegroundColor Cyan
Write-Host "[gen_dtc_pb2] Output dir: $adapterDir" -ForegroundColor Cyan

# Ensure deps
python -m pip install --upgrade pip --disable-pip-version-check | Out-Null
python -m pip install protobuf grpcio-tools --disable-pip-version-check -q | Out-Null

# Generate
python -m grpc_tools.protoc --proto_path="$protoDir" --python_out="$adapterDir" "$ProtoFile"

$produced = Join-Path $adapterDir "DTCProtocol_pb2.py"
$final = Join-Path $adapterDir "dtc_pb2.py"
if (Test-Path $produced) {
  if (Test-Path $final) { Remove-Item $final -Force }
  Rename-Item $produced $final -Force
  Write-Host "[gen_dtc_pb2] Generated $final" -ForegroundColor Green
} elseif (Test-Path $final) {
  Write-Host "[gen_dtc_pb2] Found existing $final" -ForegroundColor Yellow
} else {
  throw "grpc_tools.protoc did not produce DTCProtocol_pb2.py"
}


