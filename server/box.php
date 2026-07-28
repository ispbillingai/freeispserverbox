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
          table{border-collapse:collapse}td,th{border:1px solid #444;padding:6px 12px}
          .ok{color:#4f4}.dead{color:#f55}</style></head><body>
          <h2>FreeISP box fleet</h2><table>
          <tr><th>box</th><th>status</th><th>last seen</th><th>hotspot</th>
          <th>pppoe</th><th>router</th><th>box IP</th><th>rssi</th><th>fw</th></tr>";
    foreach (glob("$dir/hb_*.json") as $f) {
        $d = json_decode(file_get_contents($f), true);
        if (!$d) continue;
        $age = time() - ($d['ts'] ?? 0);
        $alive = $age < 120;
        printf("<tr><td>%s</td><td class='%s'>%s</td><td>%ds ago</td><td>%s</td>
                <td>%s</td><td class='%s'>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>",
            htmlspecialchars($d['box'] ?? '?'),
            $alive ? 'ok' : 'dead', $alive ? 'ALIVE' : 'DEAD/OFFLINE',
            $age,
            $d['hotspot'] ?? '-', $d['pppoe'] ?? '-',
            ($d['router'] ?? false) ? 'ok' : 'dead',
            ($d['router'] ?? false) ? 'UP' : 'DOWN',
            htmlspecialchars($d['ip'] ?? '-'),
            $d['rssi'] ?? '-', htmlspecialchars($d['fw'] ?? '-'));
    }
    echo "</table><p>red = no heartbeat for 2+ minutes (box dead, offline, or stolen)</p></body></html>";
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
