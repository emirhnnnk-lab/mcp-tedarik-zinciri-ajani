# Türkçe sentetik sesli komutlar (Windows OneCore "Tolga" sesi). Örnek veridir.
param([string]$Klasor = "$PSScriptRoot\sesler")
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Bekle($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait() | Out-Null; $task.Result }
$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$s.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq 'tr-TR' } | Select-Object -First 1
$cumleler = Get-Content "$PSScriptRoot\ses_cumleler.txt" -Encoding UTF8
$i = 0
foreach ($c in $cumleler) {
  $i++
  $akis = Bekle ($s.SynthesizeTextToStreamAsync($c)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
  $okuyucu = New-Object Windows.Storage.Streams.DataReader($akis.GetInputStreamAt(0))
  $n = Bekle ($okuyucu.LoadAsync([uint32]$akis.Size)) ([uint32])
  $bayt = New-Object byte[] $n; $okuyucu.ReadBytes($bayt)
  [IO.File]::WriteAllBytes(("{0}\komut_{1:D2}.wav" -f $Klasor, $i), $bayt)
}
"$i ses dosyasi uretildi"
