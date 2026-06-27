param(
    [string]$Title = "LectureLens",
    [int]$ChunkSeconds = 10
)

$python = ".\.venv\Scripts\python.exe"

Write-Host ""
Write-Host "[1/3] study-session 시작"
& $python -m src.cli study-session --title $Title --chunk-seconds $ChunkSeconds

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "study-session 실패. 후속 작업 중단"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[2/3] 최신 summary Notion 업로드"
& $python -m src.notion_push --latest

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Notion 업로드 실패"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[3/3] study pack + 오개념 로그 생성"
& $python -m src.study_pack --latest

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "study pack 생성 실패"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "전체 완료"
