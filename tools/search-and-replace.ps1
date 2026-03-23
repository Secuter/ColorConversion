# Set to $true to actually perform rename/replace, $false to only search and print matches
$EnableReplaceActions = $true
# PowerShell script to search for file names (without extension) in file names and file contents, with optional replace

# --- CONFIGURATION ---
# List of search/replace pairs (without extension)
$SearchPairs = @(
    @{ Search = "AK Real Colors"; Append = "Official" },
    @{ Search = "AK Real Colors Conversion"; Replace = "AK Real Colors Official" },
    @{ Search = "Ammo Mig"; Append = "Official" },
    @{ Search = "Atom Ammo Mig"; Append = "Official" },
    @{ Search = "Humbrol Color Conversion"; Replace = "Humbrol Official" },
    @{ Search = "Italeri Conversion"; Replace = "Italeri Official" },
    @{ Search = "MrColor Aqueous Conversion"; Replace = "MrColor Aqueous 2" },
    @{ Search = "MrColor Acrysion Conversion"; Replace = "MrColor Acrysion 2" },
    @{ Search = "MrColor Laquer Conversion"; Replace = "MrColor Laquer 2" },
    @{ Search = "Revell Enamel Conversion"; Replace = "Revell Enamel Official" },
    @{ Search = "Revell Acrylic Conversion"; Replace = "Revell Acrylic Official" },
    @{ Search = "Tamiya Gloss Conversion"; Replace = "Tamiya Gloss 2" },
    @{ Search = "Tamiya Conversion"; Replace = "Tamiya 2" },
    @{ Search = "Tamiya Flat Conversion"; Replace = "Tamiya Flat 2" },
    @{ Search = "RLM Conversion"; Replace = "RLM" },
    @{ Search = "Vallejo Model Air"; Append = "Official" },
    @{ Search = "Vallejo Model Color"; Append = "Official" }
)

# Paths to search for file names (recursively)
$FileNameSearchPaths = @(
    "C:\Users\diego\Documents\Modellismo\Colors",
    "C:\Projects\ColorConversion\tools\pdf-import\input",
    "C:\Projects\ColorConversion\tools\pdf-import\output"
)

# Path to search for file contents
$ContentSearchPath = "C:\Projects\ColorConversion\tools\pdf-import"


# --- REPLACE/APPEND MODE CONFIGURATION ---

# Each pair can have either Replace (for replacement) or just Search (for append mode)

# --- SEARCH LOGIC ---

Write-Host "--- Searching for file names ---"
foreach ($path in $FileNameSearchPaths) {
    foreach ($pair in $SearchPairs) {
        $searchName = $pair.Search
        $hasReplace = $pair.ContainsKey('Replace')
        if ($hasReplace) {
            $replaceName = $pair.Replace
        } else {
            $replaceName = "$searchName Append"
        }
        $files = Get-ChildItem -Path $path -Recurse -File | Where-Object { $_.BaseName -eq $searchName }
        foreach ($file in $files) {
            Write-Host "Found file: $($file.FullName)"
            $newName = Join-Path $file.DirectoryName ("$replaceName$($file.Extension)")
            if ($EnableReplaceActions) {
                Rename-Item -Path $file.FullName -NewName $newName
                Write-Host "Renamed to: $newName"
            }
        }
    }
}

Write-Host "--- Searching for file contents ---"
$allFiles = Get-ChildItem -Path $ContentSearchPath -Recurse -File
foreach ($file in $allFiles) {
    $content = Get-Content $file.FullName -Raw
    foreach ($pair in $SearchPairs) {
        $searchName = $pair.Search
        $hasReplace = $pair.ContainsKey('Replace')
        if ($hasReplace) {
            $replaceValue = $pair.Replace
        } else {
            $replaceValue = "$searchName Append"
        }
        # Regex: match $searchName as a whole word (not part of a longer word)
        $pattern = "\b$searchName\b"
        if ($content -match $pattern) {
            Write-Host "Found in content: $($file.FullName) ($searchName)"
            if ($EnableReplaceActions) {
                $newContent = $content -replace $pattern, $replaceValue
                Set-Content -Path $file.FullName -Value $newContent
                if ($hasReplace) {
                    Write-Host "Replaced '$searchName' with '$replaceValue' in $($file.FullName)"
                } else {
                    Write-Host "Appended to '$searchName' in $($file.FullName)"
                }
            }
        }
    }
}

Write-Host "--- Done ---"
