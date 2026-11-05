# TEMPORARY, for the flaky studio tests (to be removed before merging): the runner's TCP port settings, then
# every 2 s the loopback connections by state, into $env:RUNNER_TEMP\ports.txt until the job ends.
param([switch]$Report)
$file = Join-Path $env:RUNNER_TEMP "ports.txt"
if ($Report) {
  $rows = @(Get-Content $file)
  $tw = $rows | ForEach-Object { if ($_ -match " tw=(\d+)") { [int]$Matches[1] } }
  $all = $rows | ForEach-Object { if ($_ -match " all=(\d+)") { [int]$Matches[1] } }
  "samples=$($rows.Count) max loopback TIME_WAIT=$(($tw | Measure-Object -Maximum).Maximum) max all=$(($all | Measure-Object -Maximum).Maximum)"
  for ($i = 0; $i -lt $rows.Count; $i += 5) { $rows[$i] }
  return
}
netsh int ipv4 show dynamicport tcp
netsh int ipv4 show excludedportrange protocol=tcp
$loop = @'
while ($true) {
  $s = netstat -an -p tcp
  $tw = @($s | Select-String '127\.0\.0\.1.*TIME_WAIT').Count
  $est = @($s | Select-String '127\.0\.0\.1.*ESTABLISHED').Count
  $twAll = @($s | Select-String 'TIME_WAIT').Count
  $all = @($s | Select-String '^\s*TCP').Count
  Add-Content $env:PROBE_FILE ((Get-Date -Format HH:mm:ss) + " tw=$tw est=$est twall=$twAll all=$all")
  Start-Sleep 2
}
'@
$env:PROBE_FILE = $file
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($loop))
Start-Process pwsh -ArgumentList "-NoProfile", "-EncodedCommand", $encoded -WindowStyle Hidden
"probe started, writing $file"
