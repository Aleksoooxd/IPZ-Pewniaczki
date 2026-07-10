param([string]$cmd = "all")

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\..\.."   # src/flask_app/app/
$BabelCfg    = "$ScriptDir\babel.cfg"
$TransDir    = "$ProjectRoot\translations"
$PotFile     = "$TransDir\messages.pot"
$Langs       = @("pl", "en")

Push-Location $ProjectRoot

switch ($cmd) {
    "extract" {
        Write-Host "Extracting messages..." -ForegroundColor Cyan
        pybabel extract -F $BabelCfg -o $PotFile .
    }
    "update" {
        Write-Host "Extracting messages..." -ForegroundColor Cyan
        pybabel extract -F $BabelCfg -o $PotFile .
        foreach ($lang in $Langs) {
            Write-Host "Updating $lang..." -ForegroundColor Yellow
            pybabel update -i $PotFile -d $TransDir -l $lang --ignore-obsolete
        }
    }
    "compile" {
        Write-Host "Compiling translations..." -ForegroundColor Green
        pybabel compile -d $TransDir
    }
    "all" {
        Write-Host "Extracting messages..." -ForegroundColor Cyan
        pybabel extract -F $BabelCfg -o $PotFile .
        foreach ($lang in $Langs) {
            Write-Host "Updating $lang..." -ForegroundColor Yellow
            pybabel update -i $PotFile -d $TransDir -l $lang --ignore-obsolete
        }
        Write-Host "Compiling translations..." -ForegroundColor Green
        pybabel compile -d $TransDir
    }
    "init-lang" {
        $lang = Read-Host "Podaj kod języka (np. de)"
        pybabel init -i $PotFile -d $TransDir -l $lang
    }
    default {
        Write-Host "Dostepne komendy: extract | update | compile | all | init-lang" -ForegroundColor Red
    }
}

Pop-Location