$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host "ShipIQ auto-sync started. Checking GitHub every 15 seconds."
Write-Host "Keep this terminal open."

while ($true) {
    git fetch origin main --quiet

    if ($LASTEXITCODE -eq 0) {
        $behind = git rev-list --count HEAD..origin/main
        $ahead = git rev-list --count origin/main..HEAD

        if ($behind -gt 0 -and $ahead -eq 0) {
            $changes = @(git diff --name-only)
            $unsafe = @($changes | Where-Object { $_ -ne ".gitignore" })

            if ($unsafe.Count -eq 0) {
                git merge --ff-only origin/main

                if ($LASTEXITCODE -eq 0) {
                    Write-Host "ShipIQ updated from GitHub."
                }
            }
            else {
                Write-Host "Local code changes detected. Sync paused to protect them."
            }
        }
    }

    Start-Sleep -Seconds 15
}
