function $(s) { return document.querySelector(s); }

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function setStatus(text) { $('#status').textContent = text; }

async function loadStatus() {
  try {
    const s = await fetchJSON('/api/status');
    setStatus(`Running • model: ${s.model} • device: ${s.device}`);
    $('#about').textContent = `Cache: ${s.cache_dir}`;
  } catch (e) {
    setStatus('Server not reachable');
  }
}

function enableActions(enabled) {
  $('#actions').classList.toggle('hidden', !enabled);
  $('#downloadBtn').disabled = !enabled;
  $('#shareBtn').disabled = !enabled;
}

function showResult(r) {
  $('#result').classList.remove('hidden');
  $('#source').textContent = `Source: ${r.source}${r.cached ? ' (cached)' : ''}`;
  $('#model').textContent = `Model: ${r.model}`;
  $('#video').textContent = `Video ID: ${r.video_id}`;
  $('#transcript').value = r.transcript;
  $('#downloadBtn').onclick = () => {
    const a = document.createElement('a');
    a.href = `/api/download?video_id=${encodeURIComponent(r.video_id)}`;
    a.click();
  };
  $('#shareBtn').onclick = async () => {
    const text = r.transcript;
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Transcript', text });
        return;
      } catch (e) {}
    }
    try {
      await navigator.clipboard.writeText(text);
      alert('Transcript copied to clipboard');
    } catch (e) {
      alert('Sharing not supported. Copy manually.');
    }
  };
  enableActions(true);
}

function setLoading(isLoading) {
  const btn = document.querySelector('form button[type="submit"]');
  btn.disabled = isLoading;
  btn.textContent = isLoading ? 'Working…' : 'Get Transcript';
}

function initApp() {
  loadStatus();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{});
  }
  const form = document.getElementById('form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    enableActions(false);
    $('#result').classList.add('hidden');
    setLoading(true);
    const url = document.getElementById('url').value.trim();
    try {
      const r = await fetchJSON('/api/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      showResult(r);
    } catch (e) {
      alert('Error: ' + (e.message || e));
    } finally {
      setLoading(false);
    }
  });
}


