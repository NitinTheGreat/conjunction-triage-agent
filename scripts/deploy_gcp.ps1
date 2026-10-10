<#
.SYNOPSIS
Deploy the API and the Next.js app to Cloud Run in the Aeza Google Cloud project.
.DESCRIPTION
Builds both images with Cloud Build into the project's existing Artifact Registry
repository, then deploys two NEW services (conjunction-api, conjunction-web). It passes
--project explicitly, never changes the gcloud default configuration, and never touches
the project's other services (aeza-api, aeza-web).

The datasets are not uploaded and no LLM credential is deployed: the physics calculator
and the recorded examples work; the data-backed endpoints report as unavailable and live
agent analysis fails with a missing-credential error, so it cannot be billed.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_gcp.ps1
#>
[CmdletBinding()]
param(
    [string]$Project = 'aeza-brand-analytics',
    [string]$Region = 'asia-southeast1',
    [string]$Repository = 'aeza',
    [string]$ApiService = 'conjunction-api',
    [string]$WebService = 'conjunction-web'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tag = (git -C $root rev-parse --short HEAD).Trim()
$registry = "$Region-docker.pkg.dev/$Project/$Repository"

function Invoke-Gcloud {
    & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud $($args[0..1] -join ' ') failed with exit code $LASTEXITCODE" }
}

if ($ApiService -in 'aeza-api', 'aeza-web' -or $WebService -in 'aeza-api', 'aeza-web') {
    throw 'Refusing to overwrite an existing Aeza analytics service.'
}

Write-Host "Building the API image ($tag)..."
Invoke-Gcloud builds submit $root --project $Project --tag "$registry/${ApiService}:$tag" --quiet

Write-Host 'Deploying the API...'
Invoke-Gcloud run deploy $ApiService --project $Project --region $Region `
    --image "$registry/${ApiService}:$tag" --allow-unauthenticated --port 8080 `
    --cpu 1 --memory 1Gi --min-instances 0 --max-instances 2 --timeout 60 `
    --command python '--args=-m,uvicorn,api.main:app,--host,0.0.0.0,--port,8080' --quiet
$apiUrl = (& gcloud run services describe $ApiService --project $Project --region $Region --format 'value(status.url)').Trim()

Write-Host 'Syncing the static exports and building the web image...'
Push-Location (Join-Path $root 'web')
try { npm run sync-data | Out-Null } finally { Pop-Location }
Invoke-Gcloud builds submit (Join-Path $root 'web') --project $Project --tag "$registry/${WebService}:$tag" --quiet

Write-Host 'Deploying the web app...'
Invoke-Gcloud run deploy $WebService --project $Project --region $Region `
    --image "$registry/${WebService}:$tag" --allow-unauthenticated --port 8080 `
    --cpu 1 --memory 1Gi --min-instances 0 --max-instances 3 --timeout 240 `
    --set-env-vars "ORBITAL_API_URL=$apiUrl" --quiet
$webUrl = (& gcloud run services describe $WebService --project $Project --region $Region --format 'value(status.url)').Trim()

Write-Host ''
Write-Host "Web app: $webUrl"
Write-Host "Findings: $webUrl/findings"
Write-Host "API docs: $apiUrl/docs"
