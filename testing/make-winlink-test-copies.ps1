#Requires -Version 5.1
<#
.SYNOPSIS
    Writes browser-testable copies of the three Winlink Initial templates plus
    Worker-form fixtures for the Load Data / GPS tests (checklist section D).
.DESCRIPTION
    Winlink substitutes {Latitude}, {Longitude}, {GridSquare}, {GPS_SIGNED_DECIMAL}
    and {MsgSender} when it opens a template. Outside Winlink those tokens stay
    literal, so this script bakes in the values a real station would see and
    writes the results to testing\_out\ (gitignored), which the dev server at
    http://<LAN IP>:9877/testing/_out/ can serve to Chrome.

    Fixtures per form (dr, so, wcl):
      <form>_gps.txt     numeric stn_lat_d / stn_lon_d / stn_grid_d
      <form>_nogps.txt   the same keys present but blank (what a phone with no fix saves)
      <form>_nokeys.txt  GPS keys absent entirely

    In Chrome, for each template: set #parseme to a fixture, call populateForm(),
    then buildMsg(), and read stn_lat_d / stn_lon_d / stn_grid_d / loc_src.

.PARAMETER GpsSignedDecimal
    Value for {GPS_SIGNED_DECIMAL}. Default is Winlink's no-receiver text
    "(Not available)"; pass e.g. "41.9 -111.7" to simulate a live fix (test D6).
#>
param(
    [string]$Latitude  = '41.812500',
    [string]$Longitude = '-111.791667',
    [string]$Grid      = 'DN41CT',
    [string]$GpsSignedDecimal = '(Not available)',
    [string]$Callsign  = 'W9TLH-3'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Out = Join-Path $PSScriptRoot '_out'
New-Item -ItemType Directory -Force $Out | Out-Null
$enc = New-Object System.Text.UTF8Encoding $false

$templates = @{
    dr  = 'templates\disaster-report\Church_of_Jesus_Christ_Disaster_Report_Initial.html'
    so  = 'templates\supply-order\Church_of_Jesus_Christ_Supply_Order_Initial.html'
    wcl = 'templates\work-crew-log\Church_of_Jesus_Christ_Work_Crew_Log.html'
}

foreach ($k in $templates.Keys) {
    $t = [IO.File]::ReadAllText((Join-Path $RepoRoot $templates[$k]))
    $t = $t.Replace('{GPS_SIGNED_DECIMAL}', $GpsSignedDecimal).
            Replace('{Latitude}', $Latitude).
            Replace('{Longitude}', $Longitude).
            Replace('{GridSquare}', $Grid).
            Replace('{MsgSender}', $Callsign)
    [IO.File]::WriteAllText((Join-Path $Out "$k.html"), $t, $enc)
    Write-Host "  wrote $k.html"
}

# Minimal Worker-form payloads: enough fields to fill the subject line and the
# first block of each form. Field names must match the Initial templates.
$base = @{
    dr  = @{ inc_date = '2026-10-26'; inc_stake = 'Test Stake'; inc_location = '123 Main St';
             inc_type = 'Flooding'; sub_name = 'Test Volunteer'; mem_injuries = '0';
             miss_safe = 'YES'; vol_injuries = 'NO'; need_local = 'NO'; need_neighbor = 'YES'; need_hq = 'NO' }
    so  = @{ order_date = '2026-10-26'; req_stake = 'Test Stake'; del_contact = 'Test Contact';
             del_phone = '801-555-0100'; del_addr = '123 Main St'; del_city = 'Provo'; del_state = 'UT'; del_zip = '84601';
             gs02 = '3'; tl26 = '1'; kb03 = '10'; other_desc1 = 'Sump pump hose'; other_unit1 = 'each'; other_qty1 = '4';
             req_del_date = '2026-10-30'; proj_num = 'P17'; proj_name = 'Flood cleanup' }
    wcl = @{ log_date = '2026-10-26'; chief_stake = 'Test Stake'; chief_name = 'Test Chief';
             log_location = '123 Main St'; chief_hrs = '4' }
}

foreach ($k in $base.Keys) {
    $gps = $base[$k].Clone()
    $gps.stn_lat_d = '40.23380'; $gps.stn_lon_d = '-111.65850'; $gps.stn_grid_d = 'DN40CF'
    [IO.File]::WriteAllText((Join-Path $Out "${k}_gps.txt"), ($gps | ConvertTo-Json), $enc)

    $nogps = $base[$k].Clone()
    $nogps.stn_lat_d = ''; $nogps.stn_lon_d = ''; $nogps.stn_grid_d = ''
    [IO.File]::WriteAllText((Join-Path $Out "${k}_nogps.txt"), ($nogps | ConvertTo-Json), $enc)

    [IO.File]::WriteAllText((Join-Path $Out "${k}_nokeys.txt"), ($base[$k] | ConvertTo-Json), $enc)
    Write-Host "  wrote ${k}_gps.txt ${k}_nogps.txt ${k}_nokeys.txt"
}

Write-Host ""
Write-Host "  Output: $Out"
Write-Host "  Serve:  python -m http.server 9877 --bind 0.0.0.0   (from the repo root)"
Write-Host "  Open:   http://<LAN IP>:9877/testing/_out/dr.html"
