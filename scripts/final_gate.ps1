$ErrorActionPreference = "Stop"

Write-Host "[1/5] Static checks"
python scripts/static_check.py

Write-Host "[2/5] Recriando o ambiente Docker"
docker compose down --remove-orphans
docker compose up --build -d

Write-Host "[3/5] Esperando /health_check"
$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:3000/health_check" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 204) {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $healthy) {
    docker compose ps
    docker compose logs --tail=100 api
    throw "API não ficou healthy dentro do prazo."
}

docker compose ps
$env:SERVER_LOCALHOST = "localhost"

Write-Host "[4/5] Suíte completa"
python -m pytest -v
if ($LASTEXITCODE -ne 0) { throw "pytest falhou" }

Write-Host "[5/5] Stress dos dois casos críticos"
$tests = @(
    "tests/integration/transaction/test_transfer.py::TestTransfer::test_two_concurrent_transfers_cannot_spend_same_balance",
    "tests/integration/transaction/test_transfer.py::TestTransfer::test_two_concurrent_replays_execute_only_once"
)

foreach ($test in $tests) {
    for ($i = 1; $i -le 20; $i++) {
        Write-Host "  $test - rodada $i/20"
        python -m pytest -q $test
        if ($LASTEXITCODE -ne 0) { throw "Stress test falhou: $test, rodada $i" }
    }
}

Write-Host "FINAL_GATE_OK"
