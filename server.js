const express = require('express');
const http    = require('http');
const WebSocket = require('ws');
const jwt     = require('jsonwebtoken');
const bcrypt  = require('bcryptjs');
const cors    = require('cors');
const fs      = require('fs');
const path    = require('path');

// ══════════════════════════════════════════════════════════
// CONFIG  —  change these before deploying
// ══════════════════════════════════════════════════════════
const PORT          = process.env.PORT || 3000;
const JWT_SECRET    = process.env.JWT_SECRET || 'ipl2026-super-secret-change-me';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'ipl2026admin';
const DATA_FILE     = path.join(__dirname, 'draft-data.json');

// ══════════════════════════════════════════════════════════
// DEFAULT DATA
// ══════════════════════════════════════════════════════════
const TIER_PATTERN = ['PLATINUM','GOLD','SILVER','GOLD','BRONZE','PLATINUM','GOLD','SILVER','GOLD','BRONZE'];

const DEFAULT_TEAMS = [
  {name:"Mumbai Monarchs",    owner:"Owner 1"},
  {name:"Chennai Challengers",owner:"Owner 2"},
  {name:"Delhi Dynamos",      owner:"Owner 3"},
  {name:"Kolkata Knights",    owner:"Owner 4"},
  {name:"Bangalore Blasters", owner:"Owner 5"},
  {name:"Rajasthan Royals XI",owner:"Owner 6"},
  {name:"Punjab Panthers",    owner:"Owner 7"},
  {name:"Hyderabad Hawks",    owner:"Owner 8"},
  {name:"Gujarat Giants",     owner:"Owner 9"},
  {name:"Lucknow Lions",      owner:"Owner 10"},
];

const DEFAULT_PLAYERS = [
  {name:"Virat Kohli",tier:"PLATINUM",role:"BAT",ipl:"RCB"},
  {name:"Rohit Sharma",tier:"PLATINUM",role:"BAT",ipl:"MI"},
  {name:"Jasprit Bumrah",tier:"PLATINUM",role:"BWL",ipl:"MI"},
  {name:"MS Dhoni",tier:"PLATINUM",role:"WK",ipl:"CSK"},
  {name:"Hardik Pandya",tier:"PLATINUM",role:"AR",ipl:"MI"},
  {name:"Rashid Khan",tier:"PLATINUM",role:"BWL",ipl:"GT"},
  {name:"Suryakumar Yadav",tier:"PLATINUM",role:"BAT",ipl:"MI"},
  {name:"Rishabh Pant",tier:"PLATINUM",role:"WK",ipl:"LSG"},
  {name:"KL Rahul",tier:"PLATINUM",role:"WK",ipl:"LSG"},
  {name:"Shubman Gill",tier:"PLATINUM",role:"BAT",ipl:"GT"},
  {name:"Ravindra Jadeja",tier:"PLATINUM",role:"AR",ipl:"CSK"},
  {name:"Pat Cummins",tier:"PLATINUM",role:"AR",ipl:"SRH"},
  {name:"Travis Head",tier:"PLATINUM",role:"BAT",ipl:"SRH"},
  {name:"Jos Buttler",tier:"PLATINUM",role:"BAT",ipl:"RR"},
  {name:"Yashasvi Jaiswal",tier:"GOLD",role:"BAT",ipl:"RR"},
  {name:"Ruturaj Gaikwad",tier:"GOLD",role:"BAT",ipl:"CSK"},
  {name:"Sanju Samson",tier:"GOLD",role:"WK",ipl:"RR"},
  {name:"Mohammed Shami",tier:"GOLD",role:"BWL",ipl:"GT"},
  {name:"Axar Patel",tier:"GOLD",role:"AR",ipl:"DC"},
  {name:"Kagiso Rabada",tier:"GOLD",role:"BWL",ipl:"PBKS"},
  {name:"Abhishek Sharma",tier:"GOLD",role:"BAT",ipl:"SRH"},
  {name:"Glenn Maxwell",tier:"GOLD",role:"AR",ipl:"RCB"},
  {name:"Faf du Plessis",tier:"GOLD",role:"BAT",ipl:"RCB"},
  {name:"Yuzvendra Chahal",tier:"GOLD",role:"BWL",ipl:"RR"},
  {name:"Ishan Kishan",tier:"GOLD",role:"WK",ipl:"MI"},
  {name:"Trent Boult",tier:"GOLD",role:"BWL",ipl:"RR"},
  {name:"Nitish Kumar Reddy",tier:"GOLD",role:"AR",ipl:"SRH"},
  {name:"Liam Livingstone",tier:"GOLD",role:"AR",ipl:"PBKS"},
  {name:"Tilak Varma",tier:"GOLD",role:"BAT",ipl:"MI"},
  {name:"Kuldeep Yadav",tier:"GOLD",role:"BWL",ipl:"DC"},
  {name:"Washington Sundar",tier:"SILVER",role:"AR",ipl:"SRH"},
  {name:"Shardul Thakur",tier:"SILVER",role:"AR",ipl:"KKR"},
  {name:"Bhuvneshwar Kumar",tier:"SILVER",role:"BWL",ipl:"SRH"},
  {name:"Arshdeep Singh",tier:"SILVER",role:"BWL",ipl:"PBKS"},
  {name:"Krunal Pandya",tier:"SILVER",role:"AR",ipl:"LSG"},
  {name:"Shivam Dube",tier:"SILVER",role:"AR",ipl:"CSK"},
  {name:"Marcus Stoinis",tier:"SILVER",role:"AR",ipl:"LSG"},
  {name:"Devon Conway",tier:"SILVER",role:"BAT",ipl:"CSK"},
  {name:"Varun Chakaravarthy",tier:"SILVER",role:"BWL",ipl:"KKR"},
  {name:"Heinrich Klaasen",tier:"SILVER",role:"WK",ipl:"SRH"},
  {name:"Deepak Chahar",tier:"SILVER",role:"BWL",ipl:"CSK"},
  {name:"Ravi Bishnoi",tier:"SILVER",role:"BWL",ipl:"LSG"},
  {name:"Prithvi Shaw",tier:"BRONZE",role:"BAT",ipl:"DC"},
  {name:"Rinku Singh",tier:"BRONZE",role:"BAT",ipl:"KKR"},
  {name:"Noor Ahmad",tier:"BRONZE",role:"BWL",ipl:"GT"},
  {name:"Harshal Patel",tier:"BRONZE",role:"BWL",ipl:"PBKS"},
  {name:"T Natarajan",tier:"BRONZE",role:"BWL",ipl:"SRH"},
  {name:"Deepak Hooda",tier:"BRONZE",role:"AR",ipl:"LSG"},
  {name:"Umran Malik",tier:"BRONZE",role:"BWL",ipl:"SRH"},
  {name:"Ramandeep Singh",tier:"BRONZE",role:"AR",ipl:"KKR"},
];

function defaultDraft() {
  return {
    teams:   DEFAULT_TEAMS.map(t => ({...t})),
    players: DEFAULT_PLAYERS.map(p => ({...p, drafted: false})),
    picks:   [],
    cur:     0,
    updatedAt: Date.now()
  };
}

// ══════════════════════════════════════════════════════════
// PERSISTENCE  — read/write JSON file
// ══════════════════════════════════════════════════════════
function loadDraft() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
    }
  } catch(e) { console.error('Load error:', e.message); }
  return defaultDraft();
}

function saveDraft(data) {
  data.updatedAt = Date.now();
  try { fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2)); }
  catch(e) { console.error('Save error:', e.message); }
}

let draft = loadDraft();

// ══════════════════════════════════════════════════════════
// HELPERS
// ══════════════════════════════════════════════════════════
function getPickInfo(g) {
  const round = Math.floor(g / 10), p = g % 10;
  return { round, p, teamIdx: (p + round) % 10, tier: TIER_PATTERN[p], g };
}

function verifyToken(req) {
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;
  if (!token) return null;
  try { return jwt.verify(token, JWT_SECRET); }
  catch(e) { return null; }
}

function requireAdmin(req, res, next) {
  const payload = verifyToken(req);
  if (!payload || payload.role !== 'admin') {
    return res.status(401).json({ error: 'Admin access required' });
  }
  req.user = payload;
  next();
}

// ══════════════════════════════════════════════════════════
// EXPRESS APP
// ══════════════════════════════════════════════════════════
const app    = express();
const server = http.createServer(app);

app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// ── AUTH ──────────────────────────────────────────────────

// POST /api/login  — body: { password, role }
app.post('/api/login', (req, res) => {
  const { password, role } = req.body;
  if (role === 'viewer') {
    const token = jwt.sign({ role: 'viewer' }, JWT_SECRET, { expiresIn: '12h' });
    return res.json({ token, role: 'viewer' });
  }
  if (role === 'admin') {
    if (password !== ADMIN_PASSWORD) {
      return res.status(401).json({ error: 'Wrong password' });
    }
    const token = jwt.sign({ role: 'admin' }, JWT_SECRET, { expiresIn: '12h' });
    return res.json({ token, role: 'admin' });
  }
  res.status(400).json({ error: 'Invalid role' });
});

// GET /api/me  — check current token
app.get('/api/me', (req, res) => {
  const payload = verifyToken(req);
  if (!payload) return res.status(401).json({ error: 'Not authenticated' });
  res.json({ role: payload.role });
});

// ── DRAFT DATA ────────────────────────────────────────────

// GET /api/draft  — public (viewers + admins)
app.get('/api/draft', (req, res) => {
  res.json(draft);
});

// POST /api/draft/pick  — admin only
app.post('/api/draft/pick', requireAdmin, (req, res) => {
  const { playerIdx } = req.body;
  if (draft.cur >= 110) return res.status(400).json({ error: 'Draft complete' });
  const info = getPickInfo(draft.cur);
  const p = draft.players[playerIdx];
  if (!p) return res.status(400).json({ error: 'Invalid player index' });
  if (p.drafted) return res.status(400).json({ error: 'Player already drafted' });
  if (p.tier !== info.tier) return res.status(400).json({ error: `Must pick a ${info.tier} player` });

  draft.players[playerIdx] = { ...p, drafted: true };
  draft.picks.push({ ...info, pi: playerIdx, pName: p.name, pRole: p.role, pIpl: p.ipl || '—' });
  draft.cur++;
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true, draft });
});

// POST /api/draft/skip  — admin only
app.post('/api/draft/skip', requireAdmin, (req, res) => {
  if (draft.cur >= 110) return res.status(400).json({ error: 'Draft complete' });
  const info = getPickInfo(draft.cur);
  draft.picks.push({ ...info, pi: -1, pName: '— Skipped —', pRole: '', pIpl: '' });
  draft.cur++;
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true, draft });
});

// POST /api/draft/undo  — admin only
app.post('/api/draft/undo', requireAdmin, (req, res) => {
  if (!draft.picks.length) return res.status(400).json({ error: 'Nothing to undo' });
  const last = draft.picks.pop();
  if (last.pi >= 0) draft.players[last.pi] = { ...draft.players[last.pi], drafted: false };
  draft.cur = last.g;
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true, draft });
});

// PUT /api/draft/teams  — admin only: update all team names/owners
app.put('/api/draft/teams', requireAdmin, (req, res) => {
  const { teams } = req.body;
  if (!Array.isArray(teams) || teams.length !== 10) return res.status(400).json({ error: 'Need 10 teams' });
  draft.teams = teams;
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true });
});

// PUT /api/draft/players  — admin only: replace full player pool (CSV import)
app.put('/api/draft/players', requireAdmin, (req, res) => {
  const { players } = req.body;
  if (!Array.isArray(players)) return res.status(400).json({ error: 'players must be array' });
  draft.players = players.map(p => ({ ...p, drafted: false }));
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true, count: draft.players.length });
});

// POST /api/draft/players  — admin only: add single player
app.post('/api/draft/players', requireAdmin, (req, res) => {
  const { name, tier, role, ipl } = req.body;
  if (!name || !tier) return res.status(400).json({ error: 'name and tier required' });
  const validTiers = ['PLATINUM','GOLD','SILVER','BRONZE'];
  if (!validTiers.includes(tier)) return res.status(400).json({ error: 'Invalid tier' });
  draft.players.push({ name, tier, role: role||'BAT', ipl: ipl||'—', drafted: false });
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true, index: draft.players.length - 1 });
});

// DELETE /api/draft/players/:idx  — admin only
app.delete('/api/draft/players/:idx', requireAdmin, (req, res) => {
  const idx = parseInt(req.params.idx);
  if (isNaN(idx) || idx < 0 || idx >= draft.players.length) return res.status(400).json({ error: 'Invalid index' });
  if (draft.players[idx].drafted) return res.status(400).json({ error: 'Cannot remove drafted player' });
  draft.players.splice(idx, 1);
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true });
});

// POST /api/draft/reset  — admin only
app.post('/api/draft/reset', requireAdmin, (req, res) => {
  const teams = draft.teams;
  draft = defaultDraft();
  draft.teams = teams;
  saveDraft(draft);
  broadcast({ type: 'DRAFT_UPDATE', draft });
  res.json({ ok: true });
});

// GET /api/draft/export  — CSV export (admin only)
app.get('/api/draft/export', requireAdmin, (req, res) => {
  let csv = 'Round,Pick,Team,Owner,Tier,Player,Role,IPL Team\n';
  draft.picks.forEach(pk => {
    const t = draft.teams[pk.teamIdx];
    csv += `${pk.round+1},${pk.p+1},"${t.name}","${t.owner}",${pk.tier},"${pk.pName}",${pk.pRole},"${pk.pIpl}"\n`;
  });
  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', 'attachment; filename="IPL2026_Draft.csv"');
  res.send(csv);
});

// ── HEALTH ────────────────────────────────────────────────
app.get('/api/health', (req, res) => res.json({ status: 'ok', picks: draft.picks.length, cur: draft.cur }));

// ══════════════════════════════════════════════════════════
// WEBSOCKET  — real-time push to all clients
// ══════════════════════════════════════════════════════════
const wss = new WebSocket.Server({ server });

function broadcast(msg) {
  const str = JSON.stringify(msg);
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) client.send(str);
  });
}

wss.on('connection', (ws, req) => {
  console.log(`WS client connected (total: ${wss.clients.size})`);
  ws.send(JSON.stringify({ type: 'INIT', draft }));
  ws.on('close', () => console.log(`WS client disconnected (total: ${wss.clients.size})`));
  ws.on('error', e => console.error('WS error:', e.message));

  // Heartbeat
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });
});

// Heartbeat interval — detect dead connections
const heartbeat = setInterval(() => {
  wss.clients.forEach(ws => {
    if (!ws.isAlive) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);

wss.on('close', () => clearInterval(heartbeat));

// ══════════════════════════════════════════════════════════
// START
// ══════════════════════════════════════════════════════════
server.listen(PORT, () => {
  console.log(`\n🏏 IPL 2026 Draft Conductor running on port ${PORT}`);
  console.log(`   App:    http://localhost:${PORT}`);
  console.log(`   Admin:  http://localhost:${PORT}/admin.html`);
  console.log(`   API:    http://localhost:${PORT}/api/draft`);
  console.log(`   Picks:  ${draft.picks.length}/110 made\n`);
});
