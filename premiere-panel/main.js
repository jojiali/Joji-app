// Quran Arabic Bot — Premiere Pro UXP panel.
// Reads the active sequence's markers, sends the chosen colour's markers to the local
// Python bot (quran-bot/server.py), then imports the PNGs and lays them on the timeline.
const ppro = require("premierepro");

const API = "http://127.0.0.1:8765";
const $ = (id) => document.getElementById(id);

let project = null;
let sequence = null;
let groups = {};       // colorIndex -> { color, markers: [] }
let chosen = null;

function say(msg, append = false) {
  const box = $("status");
  box.classList.remove("muted");
  box.textContent = append ? box.textContent + "\n" + msg : msg;
  box.scrollTop = box.scrollHeight;
}

function css(color) {
  const k = [color.red, color.green, color.blue].some((v) => v > 1) ? 1 : 255;
  return `rgb(${Math.round(color.red * k)}, ${Math.round(color.green * k)}, ${Math.round(color.blue * k)})`;
}

const hms = (t) => new Date(Math.round(t) * 1000).toISOString().substr(11, 8);

async function readMarkers() {
  project = await ppro.Project.getActiveProject();
  sequence = project && (await project.getActiveSequence());
  if (!sequence) {
    say("Koi sequence khuli nahi hai.");
    return;
  }
  const owner = await ppro.Markers.getMarkers(sequence);
  groups = {};
  for (const m of owner.getMarkers()) {
    const i = m.getColorIndex();
    (groups[i] = groups[i] || { color: m.getColor(), markers: [] }).markers.push({
      start: m.getStart().seconds,
      duration: m.getDuration().seconds,
      name: m.getName(),
    });
  }
  const box = $("colors");
  box.innerHTML = "";
  const keys = Object.keys(groups);
  if (!keys.length) {
    say("Is sequence mein koi marker nahi.");
    return;
  }
  for (const i of keys) {
    const row = document.createElement("div");
    row.innerHTML = `<span class="swatch" style="background:${css(groups[i].color)}"></span>${groups[i].markers.length} markers`;
    row.onclick = () => {
      chosen = i;
      for (const el of box.children) el.classList.remove("on");
      row.classList.add("on");
    };
    box.appendChild(row);
  }
  say("Marker ka rang chunein, phir 'Quran PNG banao' dabayein.");
}

// Sequence time -> (media file, seconds inside it) using the clips on the audio track.
async function audioClips(trackNumber) {
  const track = await sequence.getAudioTrack(trackNumber - 1);
  const clips = [];
  for (const item of track.getTrackItems(ppro.Constants.TrackItemType.CLIP, false)) {
    const clip = ppro.ClipProjectItem.cast(await item.getProjectItem());
    clips.push({
      start: (await item.getStartTime()).seconds,
      end: (await item.getEndTime()).seconds,
      inPoint: (await item.getInPoint()).seconds,
      path: await clip.getMediaFilePath(),
    });
  }
  return clips;
}

async function startJob() {
  if (chosen === null) return say("Pehle marker ka rang chunein.");
  try {
    await fetch(API + "/health");
  } catch (e) {
    return say("Bot nahi chal raha. Pehle quran-bot\\start_bot.bat chalayein.");
  }
  const clips = await audioClips(Number($("atrack").value));
  const items = [];
  const missing = [];
  for (const m of groups[chosen].markers) {
    const c = clips.find((c) => m.start >= c.start && m.start < c.end);
    if (!c) {
      missing.push(hms(m.start));
      continue;
    }
    items.push({ media: c.path, start: c.inPoint + (m.start - c.start), duration: m.duration, seq_time: m.start, name: m.name });
  }
  if (missing.length) say(`Audio track par clip nahi mila: ${missing.join(", ")}`);
  if (!items.length) return;

  const res = await fetch(API + "/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  const { id } = await res.json();
  say(`${items.length} markers bheje. Kaam shuru…`);
  let shown = 0;
  for (;;) {
    await new Promise((r) => setTimeout(r, 2000));
    const job = await (await fetch(`${API}/jobs/${id}`)).json();
    for (; shown < job.log.length; shown++) say(job.log[shown], true);
    if (job.state === "done") return finish(job.result);
    if (job.state === "error") return;
  }
}

async function finish(result) {
  if (!result.results.length) return say("Koi Quran wala hissa nahi mila.", true);
  if (!$("place").checked) return say(`PNGs yahan hain: ${result.folder}`, true);
  const color = $("png").value;
  const vtrack = Number($("vtrack").value) - 1;
  const fallback = Number($("dur").value) || 5;
  const binName = result.folder.split(/[\\/]/).pop();

  const root = await project.getRootItem();
  project.lockedAccess(() => {
    project.executeTransaction((ca) => ca.addAction(root.createBinAction(binName, true)), "Quran bin");
  });
  const binItem = (await root.getItems()).find((i) => i.name === binName);
  const bin = binItem ? ppro.FolderItem.cast(binItem) : null;
  await project.importFiles(result.results.map((r) => r[color]), true, bin || undefined, false);

  const imported = await (bin || root).getItems();
  const editor = ppro.SequenceEditor.getEditor(sequence);
  let placed = 0;
  for (const r of result.results) {
    const file = r[color].split(/[\\/]/).pop();
    const item = imported.find((i) => i.name === file);
    if (!item) {
      say(`Import nahi mila: ${file}`, true);
      continue;
    }
    const dur = r.duration > 0.5 ? r.duration : fallback;
    try {
      project.lockedAccess(() => {
        project.executeTransaction((ca) => {
          ca.addAction(ppro.ClipProjectItem.cast(item).createSetInOutPointsAction(
            ppro.TickTime.TIME_ZERO, ppro.TickTime.createWithSeconds(dur)));
        }, "Quran PNG duration");
        project.executeTransaction((ca) => {
          ca.addAction(editor.createOverwriteItemAction(item, ppro.TickTime.createWithSeconds(r.seq_time), vtrack, 0));
        }, "Quran PNG");
      });
      placed++;
    } catch (e) {
      say(`${file}: ${e}`, true);
    }
  }
  say(`${placed} PNG timeline par V${vtrack + 1} mein lag gayin. Folder: ${result.folder}`, true);
  if (result.skipped.length) say(`${result.skipped.length} jagah Quran nahi mila — Timestamps_List.txt dekhein.`, true);
}

$("refresh").addEventListener("click", () => readMarkers().catch((e) => say(String(e))));
$("go").addEventListener("click", () => startJob().catch((e) => say(String(e))));
