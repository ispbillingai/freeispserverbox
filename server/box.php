<?php
/*
  box.php — FreeISP box fleet endpoint. ONE file, no database.

  Upload this to your PHP server (e.g. ispledger hosting), then:

  1. CHANGE $KEY below — pick any password. Put the SAME value in the
     ESP32's secrets.h as SRV_KEY.

  2. The box POSTs a heartbeat here every 20s. View your fleet at:
        https://yourserver/box.php?view=1
     Each box shows green (alive) or red (silent >2 min = dead/stolen).

  3. Send a command to a box from your browser:
        https://yourserver/box.php?box=box1&set=screen=off&key=YOURKEY
        https://yourserver/box.php?box=box1&set=screen=on&key=YOURKEY
     The box receives it on its next heartbeat (within ~20s).
     Commands are one-shot: delivered once, then cleared.
*/

$KEY = "CHANGE_ME";                 // <-- same as SRV_KEY in secrets.h

$dir = __DIR__ . "/boxdata";
if (!is_dir($dir)) { mkdir($dir, 0755, true); }

function clean($s) { return preg_replace('/[^a-zA-Z0-9_\-]/', '', $s); }

/* ---- admin: queue a command -------------------------------------- */
if (isset($_GET['set'], $_GET['box'], $_GET['key'])) {
    if ($_GET['key'] !== $KEY) { http_response_code(403); exit('bad key'); }
    $box = clean($_GET['box']);
    file_put_contents("$dir/cmd_$box.txt", trim($_GET['set']));
    exit("command '" . htmlspecialchars($_GET['set']) . "' queued for $box");
}

/* ---- fleet view -------------------------------------------------- */
if (isset($_GET['view'])) {
    echo "<html><head><title>FreeISP boxes</title><meta http-equiv='refresh' content='10'>
          <style>body{font-family:monospace;background:#111;color:#eee;padding:20px}
          table{border-collapse:collapse}td,th{border:1px solid #444;padding:6px 10px}
          th{color:#888;font-weight:normal}
          .ok{color:#4f4}.dead{color:#f55}.warn{color:#fd0}.dim{color:#666}
          .banner{background:#711;color:#fff;padding:10px;margin-bottom:14px}</style>
          </head><body>";
    if ($KEY === "CHANGE_ME") {
        echo "<div class='banner'><b>This endpoint still has the default key.</b>
              Anyone can post fake heartbeats or command your boxes. Change
              \$KEY at the top of box.php and set the same value as SRV_KEY
              in the ESP32's secrets.h.</div>";
    }
    echo "<h2>FreeISP box fleet</h2><table>
          <tr><th>box</th><th>status</th><th>last seen</th><th>alarm</th>
          <th>door</th><th>opens</th><th>silenced</th><th>tilt</th>
          <th>power</th><th>batt</th>
          <th>hotspot</th><th>pppoe</th><th>router</th><th>box IP</th>
          <th>rssi</th><th>fw</th></tr>";
    foreach (glob("$dir/hb_*.json") as $f) {
        $d = json_decode(file_get_contents($f), true);
        if (!$d) continue;
        $age   = time() - ($d['ts'] ?? 0);
        $alive = $age < 120;
        $door  = $d['door'] ?? '-';

        /* ARMED STATE, LOUDLY. A customer who forgot they switched the
           alarm off will otherwise swear the box is broken — and a box
           that reads "fine" while it is actually deaf is worse than one
           that reads "offline". Quiet (a card tap) outranks the siren
           state here for the same reason it does on the box's screen. */
        $armed = $d['armed'] ?? true;
        $quiet = (int)($d['quiet'] ?? 0);
        $state = $d['alarm'] ?? '-';
        if (!$armed) {
            $aCls = 'dead'; $aTxt = 'DISARMED';
        } elseif ($quiet > 0) {
            $aCls = 'warn'; $aTxt = sprintf('QUIET %d:%02d', $quiet / 60, $quiet % 60);
        } elseif ($state === 'SIREN' || $state === 'GRACE') {
            $aCls = 'dead';
            $aTxt = $state . ' ' . ($d['why'] ?? '');
        } elseif ($state === 'SILENT') {
            $aCls = 'warn'; $aTxt = 'SILENCED ' . ($d['why'] ?? '');
        } else {
            $aCls = 'ok';   $aTxt = 'ARMED';
        }

        /* mains: -1 means the box has no power sensing wired, which is NOT
           the same as a box running flat on its battery. */
        $mains = $d['mains'] ?? -1;
        if ($mains < 0)      { $pCls = 'dim';  $pTxt = 'n/a'; }
        elseif ($mains == 1) { $pCls = 'ok';   $pTxt = 'MAINS'; }
        else                 { $pCls = 'dead'; $pTxt = 'BATTERY'; }

        $batt = $d['batt'] ?? -1;
        $bTxt = $batt < 0 ? '-' : number_format($batt, 2) . 'V';
        $bCls = $batt < 0 ? 'dim' : ($batt < 3.4 ? 'dead' : 'ok');

        $dis = (int)($d['disarms'] ?? 0);

        printf("<tr><td>%s</td><td class='%s'>%s</td><td>%ds ago</td>
                <td class='%s'>%s</td>
                <td class='%s'>%s</td><td>%s</td><td class='%s'>%s</td><td>%s</td>
                <td class='%s'>%s</td><td class='%s'>%s</td>
                <td>%s</td><td>%s</td>
                <td class='%s'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>",
            htmlspecialchars($d['box'] ?? '?'),
            $alive ? 'ok' : 'dead', $alive ? 'ALIVE' : 'DEAD/OFFLINE',
            $age,
            $aCls, htmlspecialchars($aTxt),
            $door === 'OPEN' ? 'dead' : 'ok', htmlspecialchars($door),
            $d['opens'] ?? '-',
            $dis > 0 ? 'warn' : 'dim', $dis,
            isset($d['tilt']) ? $d['tilt'] . '&deg;' : '-',
            $pCls, $pTxt,
            $bCls, $bTxt,
            $d['hotspot'] ?? '-', $d['pppoe'] ?? '-',
            ($d['router'] ?? false) ? 'ok' : 'dead',
            ($d['router'] ?? false) ? 'UP' : 'DOWN',
            htmlspecialchars($d['ip'] ?? '-'),
            $d['rssi'] ?? '-', htmlspecialchars($d['fw'] ?? '-'));
    }
    echo "</table>
          <p class='dim'>red status = no heartbeat for 2+ minutes (box dead,
          offline, or stolen). <b>DISARMED</b> or <b>QUIET</b> in the alarm
          column means the box will not sound — that is a state, not a fault.
          <em>silenced</em> counts how many times it has been switched off or
          shut up; a box with a climbing count is worth a phone call.</p>
          <p class='dim'>commands: screen=on|off &middot; alarm=arm|disarm|clear
          &middot; siren=off|test &middot; motion=learn &middot; quiet=off
          &middot; cards=clear</p></body></html>";
    exit;
}

/* ---- heartbeat POST from a box ----------------------------------- */
$body = json_decode(file_get_contents('php://input'), true);
if (!$body || (($body['key'] ?? '') !== $KEY)) {
    http_response_code(403);
    exit(json_encode(["error" => "bad key"]));
}
unset($body['key']);
$box = clean($body['box'] ?? 'unknown');
$body['ts'] = time();
file_put_contents("$dir/hb_$box.json", json_encode($body));

/* deliver a queued command (one-shot) */
$cmdFile = "$dir/cmd_$box.txt";
$cmd = "";
if (is_file($cmdFile)) {
    $cmd = trim(file_get_contents($cmdFile));
    unlink($cmdFile);
}
header('Content-Type: application/json');
echo json_encode(["cmd" => $cmd]);
