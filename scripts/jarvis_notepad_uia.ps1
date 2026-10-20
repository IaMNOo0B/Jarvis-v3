param()

$ErrorActionPreference = "Stop"
try {
    [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $raw = [Console]::In.ReadToEnd()
    $request = $raw | ConvertFrom-Json
    $action = [string]$request.action
    $appName = [string]$request.app
    $targetName = [string]$request.target
    $text = [string]$request.text

    if ($appName -ne "notepad" -or $action -notin @("target_exists", "type_text", "verify")) {
        throw "Unsupported fixed action."
    }
    if ($action -eq "type_text" -and ($text.Length -lt 1 -or $text.Length -gt 2000)) {
        throw "Text length is outside the supported range."
    }
    if ($targetName -ne "blank document") {
        throw "Unsupported UI target."
    }

    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes

    $nativeType = @'
using System;
using System.Runtime.InteropServices;

public static class JarvisNativeInput
{
    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT
    {
        public uint type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    public static bool SendUnicode(string value)
    {
        if (String.IsNullOrEmpty(value))
            return false;

        INPUT[] inputs = new INPUT[value.Length * 2];
        for (int i = 0; i < value.Length; i++)
        {
            inputs[i * 2].type = 1;
            inputs[i * 2].U.ki.wVk = 0;
            inputs[i * 2].U.ki.wScan = value[i];
            inputs[i * 2].U.ki.dwFlags = 0x0004;

            inputs[i * 2 + 1].type = 1;
            inputs[i * 2 + 1].U.ki.wVk = 0;
            inputs[i * 2 + 1].U.ki.wScan = value[i];
            inputs[i * 2 + 1].U.ki.dwFlags = 0x0004 | 0x0002;
        }

        return SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT))) == (uint)inputs.Length;
    }
}
'@
    Add-Type -TypeDefinition $nativeType -Language CSharp | Out-Null

    $documentCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Document
    )
    $editCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit
    )
    $editorCondition = [System.Windows.Automation.OrCondition]::new($documentCondition, $editCondition)

    function Get-ElementText($element) {
        $pattern = $null
        if ($element.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
            return [string]$pattern.DocumentRange.GetText(2048)
        }
        $pattern = $null
        if ($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
            return [string]$pattern.Current.Value
        }
        return $null
    }

    function Get-NotepadEditors {
        $root = [System.Windows.Automation.AutomationElement]::RootElement
        # For top-level windows, search only direct desktop children.
        $windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children,
            [System.Windows.Automation.Condition]::TrueCondition)

        foreach ($window in $windows) {
            try {
                $title = [string]$window.Current.Name
                $processName = ""
                try {
                    $processName = (Get-Process -Id $window.Current.ProcessId -ErrorAction Stop).ProcessName
                } catch { }
                if (($title -notmatch "(?i)notepad") -and ($processName -ne "notepad")) {
                    continue
                }
                $editors = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editorCondition)
                foreach ($editor in $editors) {
                    $currentText = Get-ElementText $editor
                    if ($null -ne $currentText) {
                        [pscustomobject]@{ Window = $window; Editor = $editor; Text = $currentText }
                    }
                }
            } catch { }
        }
    }

    $editors = @(Get-NotepadEditors)
    if ($action -eq "target_exists") {
        $blank = @($editors | Where-Object { $_.Text.Length -eq 0 } | Select-Object -First 1)
        $ok = $blank.Count -gt 0
        $detail = if ($ok) { "A blank Notepad document was found." } else { "No blank Notepad document was found; existing text was left untouched." }
    }
    elseif ($action -eq "type_text") {
        # Re-check blank state immediately before typing; never replace an existing document.
        $blank = @($editors | Where-Object { $_.Text.Length -eq 0 } | Select-Object -First 1)
        if ($blank.Count -eq 0) {
            throw "No blank Notepad document is available."
        }
        $blank[0].Editor.SetFocus()
        Start-Sleep -Milliseconds 200
        if (-not [JarvisNativeInput]::SendUnicode($text)) {
            throw "Windows did not accept the complete text input."
        }
        Start-Sleep -Milliseconds 250
        $ok = $true
        $detail = "Text input was sent to the focused Notepad editor; read-back verification is required."
    }
    else {
        $matches = @($editors | Where-Object { $_.Text -ceq $text })
        $ok = $matches.Count -gt 0
        $detail = if ($ok) { "Notepad text exactly matches the requested text." } else { "Notepad read-back did not exactly match the requested text." }
    }

    @{ success = [bool]$ok; detail = [string]$detail } | ConvertTo-Json -Compress | Write-Output
    exit 0
}
catch {
    @{ success = $false; detail = "UI Automation could not safely complete this step; no internal details were exposed." } | ConvertTo-Json -Compress | Write-Output
    exit 0
}
