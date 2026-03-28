import { useState, useEffect, useRef, useCallback } from 'react'

const VISION_BASE = 'http://localhost:8001'
const ORCH_BASE   = 'http://localhost:8000'

const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0c0f; --bg2: #0f1318; --bg3: #151b22;
    --accent: #00ff88; --red: #ff3355; --yellow: #ffcc00;
    --text: #c8d6e5; --dim: #5a6a7a; --border: #1e2a35;
    --font: 'IBM Plex Mono', monospace;
  }
  body { background: var(--bg); color: var(--text); font-family: var(--font); overflow: hidden; height: 100vh; }

  .header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 20px; background: var(--bg2); border-bottom: 1px solid var(--border); height: 52px;
  }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .pulse-dot {
    width: 10px; height: 10px; border-radius: 50%; background: var(--accent);
    animation: pulse-dot 1.5s ease-in-out infinite;
  }
  @keyframes pulse-dot {
    0%,100% { opacity:1; transform:scale(1); box-shadow:0 0 0 0 rgba(0,255,136,.6); }
    50%      { opacity:.8; transform:scale(1.15); box-shadow:0 0 0 6px rgba(0,255,136,0); }
  }
  .header-title { font-size: 18px; font-weight: 700; letter-spacing: 2px; color: #fff; }
  .header-title span { color: var(--accent); }

  .badge {
    padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 700;
    letter-spacing: 1.5px; border: 1px solid; transition: all .3s;
  }
  .badge-live    { background:rgba(0,255,136,.1); border-color:var(--accent); color:var(--accent); }
  .badge-conn    { background:rgba(255,204,0,.1); border-color:var(--yellow); color:var(--yellow); }
  .badge-offline { background:rgba(255,51,85,.1); border-color:var(--red); color:var(--red); }

  .main { display: flex; height: calc(100vh - 52px); }

  .panel-feed { flex:1; position:relative; background:#000; overflow:hidden; }
  .camera-img { width:100%; height:100%; object-fit:cover; display:block; }

  .hud { position:absolute; inset:0; pointer-events:none; }
  .corner { position:absolute; width:30px; height:30px; border-color:var(--accent); border-style:solid; opacity:.7; }
  .corner.tl { top:16px; left:16px; border-width:2px 0 0 2px; }
  .corner.tr { top:16px; right:16px; border-width:2px 2px 0 0; }
  .corner.bl { bottom:16px; left:16px; border-width:0 0 2px 2px; }
  .corner.br { bottom:16px; right:16px; border-width:0 2px 2px 0; }
  .scanline {
    position:absolute; left:0; right:0; height:2px;
    background:linear-gradient(90deg,transparent,rgba(0,255,136,.5),transparent);
    animation:scan 3s linear infinite;
  }
  @keyframes scan { 0%{top:0} 100%{top:100%} }
  .hud-ts { position:absolute; bottom:12px; left:16px; font-size:11px; color:var(--accent); letter-spacing:1px; opacity:.8; }
  .hud-label { position:absolute; top:12px; left:50%; transform:translateX(-50%); font-size:11px; color:rgba(0,255,136,.6); letter-spacing:3px; }

  .no-feed { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; color:var(--dim); font-size:13px; }
  .no-feed-icon { font-size:48px; }

  .panel-alerts { width:340px; min-width:340px; border-left:1px solid var(--border); display:flex; flex-direction:column; background:var(--bg2); }
  .alerts-header { padding:14px 16px; border-bottom:1px solid var(--border); font-size:11px; letter-spacing:2px; color:var(--dim); display:flex; justify-content:space-between; align-items:center; }

  .current-alert { margin:14px; padding:14px; border-radius:6px; border:1px solid; font-size:13px; line-height:1.6; transition:all .3s; min-height:80px; word-break:break-word; }
  .alert-clear   { border-color:var(--accent); background:rgba(0,255,136,.05); color:var(--accent); }
  .alert-alert   { border-color:var(--red); background:rgba(255,51,85,.08); color:var(--red); animation:flash .5s ease 3; }
  .alert-neutral { border-color:var(--border); background:var(--bg3); color:var(--text); }
  @keyframes flash { 0%,100%{background:rgba(255,51,85,.08)} 50%{background:rgba(255,51,85,.25)} }

  .stats { display:flex; border-top:1px solid var(--border); border-bottom:1px solid var(--border); margin:0 0 4px; }
  .stat { flex:1; padding:8px 0; text-align:center; font-size:11px; color:var(--dim); border-right:1px solid var(--border); }
  .stat:last-child { border-right:none; }
  .stat-val { font-size:18px; font-weight:700; display:block; }
  .stat-green { color:var(--accent); }
  .stat-red   { color:var(--red); }

  .log-title { padding:8px 16px 4px; font-size:10px; letter-spacing:2px; color:var(--dim); }
  .event-log { flex:1; overflow-y:auto; padding:0 12px 12px; scrollbar-width:thin; scrollbar-color:var(--border) transparent; }
  .event-log::-webkit-scrollbar { width:4px; }
  .event-log::-webkit-scrollbar-thumb { background:var(--border); border-radius:2px; }

  .event-item { padding:6px 10px; margin-bottom:4px; border-radius:4px; font-size:11px; line-height:1.5; border-left:2px solid; background:var(--bg3); animation:fadeIn .3s ease; word-break:break-word; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:none} }
  .event-clear  { border-color:var(--accent); }
  .event-alert  { border-color:var(--red); }
  .event-neutral{ border-color:var(--dim); }
  .event-time   { color:var(--dim); font-size:10px; margin-right:6px; }

  .voice-section { padding:14px; border-top:1px solid var(--border); display:flex; flex-direction:column; gap:8px; }
  .query-row { display:flex; gap:6px; }
  .query-input { flex:1; padding:8px 10px; background:var(--bg3); border:1px solid var(--border); border-radius:4px; color:var(--text); font-family:var(--font); font-size:12px; outline:none; }
  .query-input:focus { border-color:var(--accent); }
  .query-submit { padding:8px 14px; background:var(--accent); color:#000; border:none; border-radius:4px; font-family:var(--font); font-size:11px; font-weight:700; cursor:pointer; letter-spacing:1px; }
  .query-submit:hover { opacity:.85; }
  .voice-btn { width:100%; padding:12px; border-radius:6px; cursor:pointer; font-family:var(--font); font-size:12px; font-weight:700; letter-spacing:2px; border:1px solid var(--accent); color:var(--accent); background:rgba(0,255,136,.05); transition:all .2s; user-select:none; display:flex; align-items:center; justify-content:center; gap:8px; }
  .voice-btn:hover { background:rgba(0,255,136,.12); }
  .voice-btn-active { background:rgba(255,51,85,.12)!important; border-color:var(--red)!important; color:var(--red)!important; animation:pulse-btn 1s ease infinite; }
  @keyframes pulse-btn { 0%,100%{box-shadow:0 0 0 0 rgba(255,51,85,.4)} 50%{box-shadow:0 0 0 8px rgba(255,51,85,0)} }
  .voice-hint { font-size:10px; color:var(--dim); text-align:center; letter-spacing:1px; }
`

function useTimestamp() {
  const [ts, setTs] = useState('')
  useEffect(() => {
    const tick = () => setTs(new Date().toLocaleTimeString('en-US', { hour12: false }))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return ts
}

function getAlertType(text) {
  if (!text) return 'neutral'
  const up = text.toUpperCase()
  if (up.startsWith('ALERT')) return 'alert'
  if (up.startsWith('CLEAR')) return 'clear'
  return 'neutral'
}

export default function App() {
  const [frame, setFrame] = useState(null)
  const [status, setStatus] = useState('connecting') // live | connecting | offline
  const [wsStatus, setWsStatus] = useState('CONNECTING')
  const [currentAlert, setCurrentAlert] = useState('Waiting for scene analysis...')
  const [events, setEvents] = useState([])
  const [countClear, setCountClear] = useState(0)
  const [countAlert, setCountAlert] = useState(0)
  const [recording, setRecording] = useState(false)
  const [query, setQuery] = useState('')

  const ts = useTimestamp()
  const orchWsRef = useRef(null)
  const mediaRecRef = useRef(null)
  const voiceWsRef = useRef(null)
  const frameFailRef = useRef(0)

  const processAlert = useCallback((text) => {
    const type = getAlertType(text)
    setCurrentAlert(text)
    if (type === 'clear') setCountClear(c => c + 1)
    if (type === 'alert') setCountAlert(c => c + 1)
    const now = new Date().toLocaleTimeString('en-US', { hour12: false })
    setEvents(prev => [{ text: text.slice(0, 120), type, time: now, id: Date.now() + Math.random() }, ...prev.slice(0, 49)])
  }, [])

  // Frame polling
  useEffect(() => {
    let active = true
    const poll = async () => {
      while (active) {
        try {
          const res = await fetch(`${VISION_BASE}/frame`)
          const data = await res.json()
          if (data.frame) {
            setFrame(`data:image/jpeg;base64,${data.frame}`)
            setStatus('live')
            frameFailRef.current = 0
          }
        } catch {
          frameFailRef.current++
          if (frameFailRef.current > 5) setStatus('offline')
        }
        await new Promise(r => setTimeout(r, 200))
      }
    }
    poll()
    return () => { active = false }
  }, [])

  // Alert WebSocket
  useEffect(() => {
    let ws, timer
    const connect = () => {
      ws = new WebSocket(`ws://localhost:8001/ws`)
      ws.onopen = () => { setWsStatus('CONNECTED'); setStatus('live') }
      ws.onmessage = (e) => { if (e.data !== 'ping') processAlert(e.data) }
      ws.onclose = () => { setWsStatus('RECONNECTING'); setStatus('connecting'); timer = setTimeout(connect, 2000) }
      ws.onerror = () => setStatus('offline')
    }
    connect()
    return () => { ws?.close(); clearTimeout(timer) }
  }, [processAlert])

  // Orchestrator text WS
  useEffect(() => {
    let ws, timer
    const connect = () => {
      ws = new WebSocket(`ws://localhost:8000/ws`)
      orchWsRef.current = ws
      ws.onmessage = (e) => processAlert(`[AI]: ${e.data}`)
      ws.onclose = () => { timer = setTimeout(connect, 3000) }
    }
    connect()
    return () => { ws?.close(); clearTimeout(timer) }
  }, [processAlert])

  const sendQuery = async () => {
    if (!query.trim()) return
    const q = query.trim()
    setQuery('')
    processAlert(`[YOU]: ${q}`)
    const ws = orchWsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(q)
    } else {
      try {
        const res = await fetch(`${ORCH_BASE}/alert`)
        const data = await res.json()
        processAlert(data.text || 'No response')
      } catch {
        try {
          const res = await fetch(`${VISION_BASE}/analyze`, { method: 'POST' })
          const data = await res.json()
          processAlert(data.text || 'ERROR: Vision agent offline')
        } catch {
          processAlert('ERROR: Cannot reach DroneWatch agents.')
        }
      }
    }
  }

  const startVoice = async () => {
    if (recording) return
    setRecording(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ws = new WebSocket(`ws://localhost:8000/voice`)
      voiceWsRef.current = ws
      ws.onopen = () => {
        const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
        mediaRecRef.current = mr
        mr.ondataavailable = (e) => {
          if (ws.readyState === WebSocket.OPEN && e.data.size > 0) ws.send(e.data)
        }
        mr.start(100)
      }
      ws.onmessage = (e) => {
        if (typeof e.data === 'string') {
          try {
            const msg = JSON.parse(e.data)
            if (msg.text) processAlert(`[Voice AI]: ${msg.text}`)
          } catch { processAlert(`[Voice AI]: ${e.data}`) }
        }
      }
      ws.onerror = () => {
        processAlert('[Voice]: Cannot connect to Orchestrator (port 8000). Using text mode.')
        stopVoice()
      }
      ws.onclose = stopVoice
    } catch (err) {
      processAlert(`[Voice Error]: ${err.message}`)
      stopVoice()
    }
  }

  const stopVoice = () => {
    setRecording(false)
    if (mediaRecRef.current?.state !== 'inactive') {
      mediaRecRef.current?.stop()
      mediaRecRef.current?.stream?.getTracks().forEach(t => t.stop())
    }
    voiceWsRef.current?.close()
    mediaRecRef.current = null
    voiceWsRef.current = null
  }

  const alertType = getAlertType(currentAlert)
  const badgeClass = status === 'live' ? 'badge badge-live' : status === 'offline' ? 'badge badge-offline' : 'badge badge-conn'

  return (
    <>
      <style>{STYLES}</style>
      <header className="header">
        <div className="header-left">
          <div className="pulse-dot" />
          <span className="header-title">Drone<span>Watch</span></span>
        </div>
        <span className={badgeClass}>{status.toUpperCase()}</span>
      </header>

      <main className="main">
        {/* Camera Feed */}
        <section className="panel-feed">
          {!frame && (
            <div className="no-feed">
              <div className="no-feed-icon">🛸</div>
              <div>Connecting to Vision Agent...</div>
              <div style={{ fontSize: '11px', color: '#3a4a5a' }}>localhost:8001</div>
            </div>
          )}
          {frame && <img className="camera-img" src={frame} alt="Live camera feed" />}
          <div className="hud">
            <div className="corner tl" /><div className="corner tr" />
            <div className="corner bl" /><div className="corner br" />
            <div className="scanline" />
            <div className="hud-label">DRONEWATCH · LIVE</div>
            <div className="hud-ts">{ts}</div>
          </div>
        </section>

        {/* Alerts Panel */}
        <aside className="panel-alerts">
          <div className="alerts-header">
            <span>ALERT FEED</span>
            <span style={{ color: wsStatus === 'CONNECTED' ? 'var(--accent)' : 'var(--yellow)' }}>{wsStatus}</span>
          </div>

          <div className={`current-alert alert-${alertType}`}>{currentAlert}</div>

          <div className="stats">
            <div className="stat"><span className="stat-val stat-green">{countClear}</span>CLEAR</div>
            <div className="stat"><span className="stat-val stat-red">{countAlert}</span>ALERT</div>
            <div className="stat"><span className="stat-val">{countClear + countAlert}</span>TOTAL</div>
          </div>

          <div className="log-title">EVENT LOG</div>
          <div className="event-log">
            {events.map(ev => (
              <div key={ev.id} className={`event-item event-${ev.type}`}>
                <span className="event-time">{ev.time}</span>{ev.text}
              </div>
            ))}
          </div>

          <div className="voice-section">
            <div className="query-row">
              <input
                className="query-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && sendQuery()}
                placeholder="Ask DroneWatch..."
              />
              <button className="query-submit" onClick={sendQuery}>ASK</button>
            </div>
            <button
              className={`voice-btn${recording ? ' voice-btn-active' : ''}`}
              onMouseDown={startVoice}
              onMouseUp={stopVoice}
              onMouseLeave={() => recording && stopVoice()}
              onTouchStart={e => { e.preventDefault(); startVoice() }}
              onTouchEnd={stopVoice}
            >
              <span>🎤</span>
              <span>{recording ? 'LISTENING...' : 'HOLD TO TALK'}</span>
            </button>
            <div className="voice-hint">Barge-in supported · Powered by Gemini Live API</div>
          </div>
        </aside>
      </main>
    </>
  )
}
