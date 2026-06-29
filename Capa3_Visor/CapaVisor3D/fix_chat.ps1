$file = "MainWindow.xaml.cs"
$lines = Get-Content $file

# Find AddProximityChatMessage and UpdatePopupPosition
$start = -1
$end = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'private void AddProximityChatMessage' -and $start -eq -1) { $start = $i }
    if ($lines[$i] -match 'private void UpdatePopupPosition' -and $end -eq -1) { $end = $i; break }
}

$replacement = Get-Content "AddProxChatFixed.cs.snippet" -Raw

$before = $lines[0..($start-1)]
$after = $lines[$end..($lines.Count-1)]
$newContent = ($before -join [char]10) + [char]10 + $replacement + [char]10 + ($after -join [char]10)
[System.IO.File]::WriteAllText($file, $newContent, [System.Text.Encoding]::UTF8)
Write-Host "Done. Lines from start: $($start+1), end: $($end+1)"
