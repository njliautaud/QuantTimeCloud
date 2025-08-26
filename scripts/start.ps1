param(
  [int]$Rows = 5000,
  [int]$Port = 8501
)

$python = "python"

$sim = Start-Process -PassThru -FilePath $python -ArgumentList "scripts/ingest.py --simulate --publish"
Start-Sleep -Seconds 1
$collector = Start-Process -PassThru -FilePath $python -ArgumentList "scripts/serve_collector.py --max-rows $Rows"

try {
  & $python -m streamlit run sierraflow/dashboard/app.py --server.port $Port --server.address 0.0.0.0
}
finally {
  if ($collector -ne $null) { Stop-Process -Id $collector.Id -Force }
  if ($sim -ne $null) { Stop-Process -Id $sim.Id -Force }
}


