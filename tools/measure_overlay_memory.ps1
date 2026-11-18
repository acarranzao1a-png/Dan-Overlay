# measure_overlay_memory.ps1 -- real memory footprint of the overlay.
#
# The .exe on its own is misleading: pywebview hosts WebView2, which runs several
# msedgewebview2.exe child processes, and those usually use far more memory than
# the Python host. This walks the process tree from the overlay and sums it.
#
# Usage:
#   powershell -File tools\measure_overlay_memory.ps1
#   powershell -File tools\measure_overlay_memory.ps1 -Watch 30
#   powershell -File tools\measure_overlay_memory.ps1 -Baseline
#
# -Baseline records the current WebView2 usage as a reference and prints the delta,
# which is the only reliable number when other apps (browser, IDE, Teams) also run
# WebView2 processes.

param(
    [string]$Name = "*DanOverlay*",
    [int]$Watch = 0,
    [switch]$Baseline
)

$BaselineFile = Join-Path $env:TEMP 'danoverlay_mem_baseline.txt'

function Get-OverlayTree {
    param([string]$Pattern)

    $roots = Get-Process -Name $Pattern -ErrorAction SilentlyContinue
    if (-not $roots) { return @() }

    $seen = @{}
    $queue = New-Object System.Collections.Queue
    foreach ($p in $roots) { $queue.Enqueue($p) }

    $result = @()
    $sawWebView = $false
    while ($queue.Count -gt 0) {
        $p = $queue.Dequeue()
        if ($seen.ContainsKey($p.Id)) { continue }
        $seen[$p.Id] = $true
        if ($p.ProcessName -eq 'msedgewebview2') { $sawWebView = $true }
        $result += $p
        try {
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" -ErrorAction SilentlyContinue
            foreach ($c in $children) {
                $cp = Get-Process -Id $c.ProcessId -ErrorAction SilentlyContinue
                if ($cp) { $queue.Enqueue($cp) }
            }
        } catch { }
    }

    # WebView2 children can be re-parented away from the host process, in which
    # case the tree walk misses them. Only then fall back to every live
    # msedgewebview2, which may include other applications.
    if (-not $sawWebView) {
        foreach ($w in (Get-Process -Name 'msedgewebview2' -ErrorAction SilentlyContinue)) {
            if (-not $seen.ContainsKey($w.Id)) {
                $seen[$w.Id] = $true
                $result += $w
            }
        }
    }
    return $result
}

function Get-Snapshot {
    param([string]$Pattern)

    $procs = Get-OverlayTree -Pattern $Pattern
    if (-not $procs -or $procs.Count -eq 0) { return $null }

    $rows = $procs | ForEach-Object {
        [pscustomobject]@{
            Name = $_.ProcessName
            PID  = $_.Id
            MB   = [math]::Round($_.WorkingSet64 / 1MB, 1)
        }
    } | Sort-Object MB -Descending

    $total = ($rows | Measure-Object MB -Sum).Sum
    $hostMB = ($rows | Where-Object { $_.Name -match 'DanOverlay' } | Measure-Object MB -Sum).Sum
    if (-not $hostMB) { $hostMB = 0 }
    return [pscustomobject]@{
        Rows    = $rows
        Total   = $total
        Host    = $hostMB
        WebView = $total - $hostMB
        Count   = $rows.Count
    }
}

function Show-Snapshot {
    param([string]$Pattern)

    $snap = Get-Snapshot -Pattern $Pattern
    if (-not $snap) {
        Write-Host "  no hay ningun proceso '$Pattern' en ejecucion" -ForegroundColor Yellow
        return
    }

    Write-Host ""
    Write-Host ("  {0,-22} {1,8} {2,10}" -f 'proceso', 'PID', 'MB')
    foreach ($r in $snap.Rows) {
        Write-Host ("  {0,-22} {1,8} {2,10:N1}" -f $r.Name, $r.PID, $r.MB)
    }
    Write-Host ("  " + ("-" * 42))
    Write-Host ("  {0,-22} {1,8} {2,10:N1}" -f 'TOTAL', $snap.Count, $snap.Total) -ForegroundColor Cyan
    Write-Host ("  {0,-22} {1,8} {2,10:N1}" -f '  host (DanOverlay)', '', [double]$snap.Host)
    Write-Host ("  {0,-22} {1,8} {2,10:N1}" -f '  WebView2', '', [double]$snap.WebView)
    Write-Host ""

    if ($Baseline -and $snap.WebView -gt 0) {
        if (Test-Path $BaselineFile) {
            $base = [double](Get-Content $BaselineFile -ErrorAction SilentlyContinue)
            if ($base -gt 0) {
                Write-Host ("  baseline guardado: {0:N1} MB  ->  delta del overlay: {1:+0.0;-0.0} MB" -f $base, ($snap.WebView - $base)) -ForegroundColor Green
            }
        } else {
            $snap.WebView | Set-Content $BaselineFile
            Write-Host ("  baseline guardado: {0:N1} MB (cierra el overlay y vuelve a medir con -Baseline)" -f $snap.WebView) -ForegroundColor Green
        }
    }
}

if ($Watch -le 0) {
    Show-Snapshot -Pattern $Name
} else {
    while ($true) {
        Write-Host ("=== " + (Get-Date -Format 'HH:mm:ss') + " ===")
        Show-Snapshot -Pattern $Name
        Start-Sleep -Seconds $Watch
    }
}
