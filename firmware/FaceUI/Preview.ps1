# Render a home-screen layout preview using the same GFX bitmap fonts.
# This is a desktop preview, not a photograph of the connected display.
param([string]$OutputPath = "$PSScriptRoot/home-preview.png")
Add-Type -AssemblyName System.Drawing
$bitmap = [System.Drawing.Bitmap]::new(480,320)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$fontRoot = 'C:/Users/magom/Documents/Arduino/libraries/Adafruit_GFX_Library/Fonts'
$fontCache = @{}
function Colour($hex) { [System.Drawing.ColorTranslator]::FromHtml($hex) }
function Rect($x,$y,$w,$h,$c) {
  $brush = [System.Drawing.SolidBrush]::new((Colour $c))
  $graphics.FillRectangle($brush,$x,$y,$w,$h); $brush.Dispose()
}
function Round($x,$y,$w,$h,$r,$c) {
  Rect ($x+$r) $y ($w-2*$r) $h $c
  Rect $x ($y+$r) $w ($h-2*$r) $c
  $brush=[System.Drawing.SolidBrush]::new((Colour $c))
  foreach($px in @($x,($x+$w-2*$r))) {
    foreach($py in @($y,($y+$h-2*$r))) {
      $graphics.FillEllipse($brush,$px,$py,(2*$r),(2*$r))
    }
  }
  $brush.Dispose()
}
function Label($x,$baseline,$font,$c,$value) {
  if (!$fontCache.ContainsKey($font)) {
    $source=Get-Content "$fontRoot/$font.h" -Raw
    $parts=$source -split 'const GFXglyph'
    $bytes=@([regex]::Matches(($parts[0] -split '\{',2)[1],'0x([0-9A-Fa-f]{2})') | ForEach-Object {[Convert]::ToInt32($_.Groups[1].Value,16)})
    # Keep match objects to preserve signed offsets and avoid font substitution.
    $glyphs=[regex]::Matches($parts[1],'\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(-?\d+),\s*(-?\d+)\s*\}')
    $fontCache[$font]=@{Bytes=$bytes;Glyphs=$glyphs}
  }
  $f=$fontCache[$font]; $colour=Colour $c
  foreach($ch in $value.ToCharArray()) {
    $g=$f.Glyphs[([int]$ch)-32].Groups
    $offset=[int]$g[1].Value; $w=[int]$g[2].Value; $h=[int]$g[3].Value
    $dx=[int]$g[5].Value; $dy=[int]$g[6].Value
    for($yy=0;$yy -lt $h;$yy++) { for($xx=0;$xx -lt $w;$xx++) {
      $bit=$yy*$w+$xx
      if(($f.Bytes[$offset+[int][Math]::Floor($bit/8)] -band (1 -shl (7-($bit%8)))) -ne 0) {
        $px=$x+$dx+$xx; $py=$baseline+$dy+$yy
        if($px -ge 0 -and $px -lt 480 -and $py -ge 0 -and $py -lt 320){$bitmap.SetPixel($px,$py,$colour)}
      }
    }}
    $x += [int]$g[4].Value
  }
}
$bg='#F2F3F8'; $card='#FFFFFF'; $ink='#191D26'; $muted='#6F7786'
$blue='#0070F5'; $green='#289A56'; $amber='#A8691B'; $edge='#DEE2EA'
$regular='FreeSans9pt7b'; $bold='FreeSansBold9pt7b'; $title='FreeSansBold12pt7b'
$graphics.Clear((Colour $bg))
Round 17 26 5 11 2 $blue; Round 25 19 5 18 2 $blue; Round 33 12 5 25 2 $blue
Label 49 35 $title $ink 'FreeISP'; Label 160 34 $regular $muted 'Overview'
Round 358 14 106 28 14 $card; Round 369 25 6 6 3 $amber; Label 383 34 $regular $amber 'Offline'
Round 16 58 448 106 14 $card; Round 16 76 3 70 1 $blue
Label 32 85 $regular $muted 'Connected users'; Label 29 141 'FreeSansBold24pt7b' $ink '42'
Label 98 137 $regular $muted 'users'; Rect 276 77 1 68 $edge
Label 296 85 $regular $muted 'Sessions'; Label 293 138 'FreeSansBold18pt7b' $blue '17'
Label 344 137 $regular $muted 'active'
Label 18 186 $bold $ink 'Ethernet'; Label 361 185 $regular $muted 'Preview data'
for($i=0;$i -lt 5;$i++) {
  $x=16+$i*92; $active=$i -ne 3; $stateColour=if($active){$green}else{$muted}
  Round $x 194 80 61 10 $card; Round ($x+59) 205 6 6 3 $stateColour
  Label ($x+12) 220 $title $(if($active){$ink}else{$muted}) ([string]($i+1))
  Label ($x+12) 244 $regular $stateColour $(if($active){'Active'}else{'Idle'})
}
Round 16 270 448 44 14 $blue
for($i=0;$i -lt 3;$i++){ $y=283+$i*8; Rect 32 $y 22 2 $card; Rect (36+($i%2)*10) ($y-3) 4 8 $card }
Label 70 299 $title $card 'Settings'
for($i=0;$i -lt 6;$i++){Rect (437+$i) (286+$i) 2 2 $card; Rect (437+$i) (296-$i) 2 2 $card}
$bitmap.Save($OutputPath,[System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose(); $bitmap.Dispose()
Write-Output $OutputPath
