function Get-VASHandoffValue {
    param($Object, [string]$Name, $Default = $null)
    if ($null -eq $Object) { return $Default }
    if ($Object -is [Collections.IDictionary]) { return $(if ($Object.Contains($Name)) { $Object[$Name] } else { $Default }) }
    $property = $Object.PSObject.Properties[$Name]
    return $(if ($null -eq $property) { $Default } else { $property.Value })
}

function Read-VASHandoffJson {
    param([string]$Path, [int]$MaximumBytes = 2097152)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    if ((Get-Item -LiteralPath $Path).Length -gt $MaximumBytes) { return $null }
    try { return ([IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) | ConvertFrom-Json) } catch { return $null }
}

function Get-VASHandoffContext {
    param([string]$Root, $Project)
    if ($null -eq $Project) {
        return [ordered]@{
            requirements = [ordered]@{ included = $false }
            design = [ordered]@{ included = $false }
            rag = [ordered]@{ included = $false; items = @() }
            preferences = [ordered]@{ included = $false; items = @() }
        }
    }
    $path = Resolve-VASRegisteredProjectPath -Root $Root -Project $Project
    $requirements = Read-VASHandoffJson (Join-Path $path 'rag-context.json')
    $design = Read-VASHandoffJson (Join-Path $path 'design-tokens.json') 262144
    $ragItems = @()
    $knowledge = Read-VASHandoffJson (Join-Path $Root 'workspace\.vas\project-knowledge.json') 20971520
    if ([bool](Get-VASHandoffValue $Project 'indexEnabled' (Get-VASHandoffValue $Project 'createIndex' $false)) -and $null -ne $knowledge) {
        $entries = Get-VASHandoffValue $knowledge 'entries' @()
        $ragItems = @($entries | Where-Object { [string](Get-VASHandoffValue $_ 'projectId' '') -eq [string]$Project.projectId } | Select-Object -First 5 | ForEach-Object {
            [ordered]@{
                title = [string](Get-VASHandoffValue $_ 'title' '')
                source = [string](Get-VASHandoffValue $_ 'source' '')
                line = [int](Get-VASHandoffValue $_ 'line' 0)
                excerpt = [string](Get-VASHandoffValue $_ 'text' '')
            }
        })
    }
    return [ordered]@{
        requirements = [ordered]@{ included = ($null -ne $requirements); value = $requirements }
        design = [ordered]@{ included = ($null -ne $design); tokens = $design }
        rag = [ordered]@{ included = ($ragItems.Count -gt 0); items = $ragItems }
        preferences = [ordered]@{ included = $false; items = @() }
    }
}

function Resolve-VASHandoffInput {
    param([string]$Root, $Body)
    $selectionId = [string](Get-VASHandoffValue $Body 'selectionId' '')
    $projectId = [string](Get-VASHandoffValue $Body 'projectId' '')
    if ([string]::IsNullOrWhiteSpace($selectionId) -eq [string]::IsNullOrWhiteSpace($projectId)) { throw 'HANDOFF_INPUT_INVALID' }
    if ($projectId) {
        $project = Get-VASProjectRecord -Root $Root -ProjectId $projectId
        if ($null -eq $project) { throw 'VAS_PROJECT_NOT_FOUND' }
        $source = Resolve-VASRegisteredProjectPath -Root $Root -Project $project
        return [ordered]@{
            source = $source; project = $project; projectName = $project.name
            sourceType = 'registered'; goal = $project.goal
        }
    }
    $source = Resolve-VASSelection -Root $Root -SelectionId $selectionId -Path ''
    return [ordered]@{
        source = $source; project = $null; projectName = [IO.Path]::GetFileName($source.TrimEnd('\'))
        sourceType = 'existing'; goal = [string](Get-VASHandoffValue $Body 'goal' 'unspecified')
    }
}

function New-VASHandoffCliRequest {
    param([string]$Root, $Body, [string]$Output = '')
    $resolved = Resolve-VASHandoffInput $Root $Body
    $mode = [string](Get-VASHandoffValue $Body 'mode' 'metadata')
    if ($mode -notin @('metadata', 'reviewed-source')) { throw 'HANDOFF_INPUT_INVALID' }
    $format = [string](Get-VASHandoffValue $Body 'format' 'json')
    if ($format -notin @('json', 'reviewed-zip')) { throw 'HANDOFF_INPUT_INVALID' }
    $approved = @(Get-VASHandoffValue $Body 'approvedFiles' @())
    if ($approved.Count -gt 100) { throw 'HANDOFF_TOO_LARGE' }
    $context = Get-VASHandoffContext $Root $resolved.project
    $requestedContext = Get-VASHandoffValue $Body 'context' $null
    if ($null -ne $requestedContext) {
        $requestedRequirements = Get-VASHandoffValue $requestedContext 'requirements' $null
        $requestedDesign = Get-VASHandoffValue $requestedContext 'design' $null
        $requestedRag = Get-VASHandoffValue $requestedContext 'rag' $null
        $requestedContinuation = Get-VASHandoffValue $requestedContext 'continuation' $null
        if ($null -ne $requestedRequirements) { $context.requirements = $requestedRequirements }
        if ($null -ne $requestedDesign) { $context.design = $requestedDesign }
        if ($null -ne $requestedContinuation) { $context.continuation = $requestedContinuation }
        if ($null -ne $requestedRag) {
            $approvedRag = @(Get-VASHandoffValue $requestedRag 'items' @() | Where-Object {
                [bool](Get-VASHandoffValue $_ 'userApproved' $false)
            } | Select-Object -First 3)
            $context.rag = [ordered]@{ included = ($approvedRag.Count -gt 0); items = $approvedRag }
        }
    }
    if ($null -eq $context.rag) { $context.rag = [ordered]@{ included = $false; items = @() } }
    $context.preferences = [ordered]@{ included = $false; items = @() }
    return [ordered]@{
        source = $resolved.source
        sourceType = $resolved.sourceType
        projectName = [string](Get-VASHandoffValue $Body 'projectName' $resolved.projectName)
        goal = $resolved.goal
        summary = [string](Get-VASHandoffValue $Body 'summary' '')
        task = Get-VASHandoffValue $Body 'task' ([ordered]@{ request = ''; constraints = @(); acceptanceCriteria = @() })
        context = $context
        workflow = Get-VASHandoffValue $Body 'workflow' ([ordered]@{ iteration = 1; parentResultId = $null })
        ragReviewed = [bool](Get-VASHandoffValue $Body 'ragReviewed' $true)
        mode = $mode
        snapshotId = [string](Get-VASHandoffValue $Body 'snapshotId' '')
        format = $format
        approvedFiles = $approved
        output = $Output
    }
}

function Invoke-VASHandoffCli {
    param([string]$Root, [string]$Action, $Body, [string]$Output = '')
    $script = Join-Path $PSScriptRoot 'vas_agent_handoff.py'
    if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'HANDOFF_MODULE_UNAVAILABLE' }
    $python = Find-VASPythonCommand
    if ($null -eq $python) { throw 'PYTHON_UNAVAILABLE' }
    $requestFile = Join-Path ([IO.Path]::GetTempPath()) ('vas-handoff-' + [Guid]::NewGuid().ToString('N') + '.json')
    try {
        $request = New-VASHandoffCliRequest $Root $Body $Output
        [IO.File]::WriteAllText($requestFile, ($request | ConvertTo-Json -Depth 24), [Text.UTF8Encoding]::new($false))
        $arguments = @($python.Prefix) + @($script, $Action, '--request', $requestFile)
        $execution = Invoke-VASPythonUtf8 $python.File $arguments
        try { $result = $execution.Output | ConvertFrom-Json } catch { throw 'HANDOFF_RESPONSE_INVALID' }
        if ($execution.ExitCode -ne 0) { throw ('HANDOFF_CLI:' + [string](Get-VASHandoffValue $result 'code' 'handoff_failed')) }
        return $result
    } finally {
        if (Test-Path -LiteralPath $requestFile) { Remove-Item -LiteralPath $requestFile -Force }
    }
}

function Get-VASAgentHandoffPreview {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)]$Body)
    return (Invoke-VASHandoffCli $Root 'preview' $Body)
}

function Export-VASAgentHandoff {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)]$Body)
    $format = [string](Get-VASHandoffValue $Body 'format' 'json')
    $suffix = if ($format -eq 'reviewed-zip') { '.zip' } else { '.json' }
    $output = Join-Path ([IO.Path]::GetTempPath()) ('vas-handoff-' + [Guid]::NewGuid().ToString('N') + $suffix)
    try {
        $result = Invoke-VASHandoffCli $Root 'export' $Body $output
        if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { throw 'HANDOFF_OUTPUT_MISSING' }
        return [ordered]@{ fileName = [string]$result.fileName; contentType = [string]$result.contentType; bytes = [IO.File]::ReadAllBytes($output) }
    } finally {
        if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Force }
    }
}

function Get-VASAgentHandoffError {
    param([string]$Message)
    if ($Message -match 'source_changed') { return [ordered]@{ status = 409; code = 'source_changed'; message = '분석 후 원본이 변경되었습니다. 다시 분석하세요.' } }
    if ($Message -match 'handoff_too_large|HANDOFF_TOO_LARGE') { return [ordered]@{ status = 413; code = 'handoff_too_large'; message = '선택한 전달 내용이 안전한 크기 한도를 초과했습니다.' } }
    if ($Message -match 'unsafe_selection') { return [ordered]@{ status = 422; code = 'unsafe_selection'; message = '선택한 파일에 전달할 수 없는 내용이 있습니다. 파일 선택을 다시 확인하세요.' } }
    if ($Message -match 'PYTHON_UNAVAILABLE') { return [ordered]@{ status = 503; code = 'python_unavailable'; message = '소스 전달팩에는 Python 3.10 이상이 필요합니다.' } }
    if ($Message -match 'VAS_PROJECT_NOT_FOUND') { return [ordered]@{ status = 404; code = 'project_not_found'; message = '프로젝트를 찾을 수 없습니다.' } }
    if ($Message -match 'selection|HANDOFF_INPUT_INVALID') { return [ordered]@{ status = 400; code = 'selection_invalid'; message = '폴더 선택 정보가 유효하지 않습니다. 다시 선택하세요.' } }
    return [ordered]@{ status = 422; code = 'handoff_failed'; message = '안전한 AI 전달팩을 만들지 못했습니다. 전달 내용을 다시 확인하세요.' }
}
