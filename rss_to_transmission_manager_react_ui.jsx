import React, { useEffect, useState, useRef } from 'react';

// RSS → Transmission Manager
// Single-file React component meant to be dropped into a React+Tailwind project.
// - Uses fetch to talk to a backend API (you must implement the server)
// - UI allows: add feed (name, url, interval minutes), list feeds, edit, delete
// - Manual check, view logs, send detected items to Transmission
// - Transmission settings stored in UI and sent to backend when adding/sending jobs

// Expected backend API endpoints (HTTP JSON):
// GET  /api/feeds                -> [{id,name,url,interval,enabled,lastChecked,lastStatus}]
// POST /api/feeds                -> {name,url,interval}  => creates feed
// PUT  /api/feeds/:id            -> {name,url,interval,enabled}
// DELETE /api/feeds/:id
// POST /api/feeds/:id/check      -> triggers immediate check, returns {newItems:[], log:...}
// GET  /api/feeds/:id/logs       -> [{ts, level, msg}]
// POST /api/feeds/:id/send       -> {itemId, downloadDir}  -> triggers Transmission add
// GET  /api/feeds/:id/status     -> {lastChecked,lastStatus,newCount}
// The backend will handle RSS parsing, dedupe, saving state, and Transmission RPC.

export default function RssTransmissionManager() {
  const [feeds, setFeeds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', url: '', interval: 10, enabled: true });
  const [selectedLogs, setSelectedLogs] = useState([]);
  const [logFeed, setLogFeed] = useState(null);
  const [transSettings, setTransSettings] = useState(() => {
    try { return JSON.parse(localStorage.getItem('tr_settings')) || { rpcUrl: '', downloadDir: '/data' }; } catch(e){return {rpcUrl:'',downloadDir:'/data'}}
  });
  const [toast, setToast] = useState(null);
  const pollRef = useRef(null);

  useEffect(() => { fetchFeeds(); startPollingStatus(); return stopPollingStatus; }, []);

  function startPollingStatus(){
    pollRef.current = setInterval(()=>{
      fetchFeeds();
    }, 15000);
  }
  function stopPollingStatus(){ if(pollRef.current) clearInterval(pollRef.current); }

  async function fetchFeeds(){
    setLoading(true);
    try{
      const res = await fetch('/api/feeds');
      if(!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setFeeds(data);
    }catch(e){ console.error(e); showToast('Failed to load feeds: '+e.message, 'error'); }
    setLoading(false);
  }

  function showToast(msg, type='info'){ setToast({msg,type}); setTimeout(()=>setToast(null),4000); }

  function openNew(){ setEditing(null); setForm({name:'',url:'',interval:10,enabled:true}); setShowForm(true); }
  function openEdit(f){ setEditing(f); setForm({name:f.name,url:f.url,interval:f.interval,enabled:!!f.enabled}); setShowForm(true); }

  async function submitForm(e){
    e.preventDefault();
    try{
      const method = editing ? 'PUT' : 'POST';
      const url = editing ? `/api/feeds/${editing.id}` : '/api/feeds';
      const res = await fetch(url, {method, headers:{'content-type':'application/json'}, body: JSON.stringify(form)});
      if(!res.ok) throw new Error(await res.text());
      await fetchFeeds();
      setShowForm(false);
      showToast(editing? 'Feed updated':'Feed added','success');
    }catch(e){ showToast('Save failed: '+e.message,'error'); }
  }

  async function removeFeed(id){ if(!confirm('Delete this feed?')) return; try{ const res = await fetch(`/api/feeds/${id}`,{method:'DELETE'}); if(!res.ok) throw new Error(await res.text()); await fetchFeeds(); showToast('Deleted','success'); }catch(e){ showToast('Delete failed: '+e.message,'error'); } }

  async function triggerCheck(id){ try{ const res = await fetch(`/api/feeds/${id}/check`,{method:'POST'}); if(!res.ok) throw new Error(await res.text()); const data = await res.json(); showToast(`Check done, new items: ${data.newItems?.length || 0}`,'success'); await fetchFeeds(); }catch(e){ showToast('Check failed: '+e.message,'error'); } }

  async function openLogs(id){ setLogFeed(id); try{ const res = await fetch(`/api/feeds/${id}/logs`); if(!res.ok) throw new Error(await res.text()); const data = await res.json(); setSelectedLogs(data); }catch(e){ showToast('Load logs failed: '+e.message,'error'); } }

  async function sendToTransmission(id, item){
    try{
      const payload = { itemId: item.id, downloadDir: transSettings.downloadDir };
      const res = await fetch(`/api/feeds/${id}/send`,{method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload)});
      if(!res.ok) throw new Error(await res.text());
      showToast('Sent to Transmission','success');
      await fetchFeeds();
    }catch(e){ showToast('Send failed: '+e.message,'error'); }
  }

  function saveTransSettings(){ localStorage.setItem('tr_settings', JSON.stringify(transSettings)); showToast('Saved Transmission settings','success'); }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">RSS → Transmission Manager</h1>
        <div className="flex gap-2">
          <button onClick={openNew} className="px-3 py-1 bg-sky-600 text-white rounded shadow">Add Feed</button>
          <button onClick={fetchFeeds} className="px-3 py-1 border rounded">Refresh</button>
        </div>
      </div>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="col-span-2">
          <div className="bg-white rounded shadow p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">Feeds</h2>
              <div className="text-sm text-slate-500">Auto-refresh every 15s</div>
            </div>
            {loading ? <div>Loading...</div> : (
              <div className="space-y-3">
                {feeds.length === 0 && <div className="text-slate-500">No feeds added yet.</div>}
                {feeds.map(feed => (
                  <div key={feed.id} className="border rounded p-3 flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <div className={`text-xs px-2 py-1 rounded ${feed.enabled? 'bg-green-100 text-green-800':'bg-red-100 text-red-800'}`}>{feed.enabled? 'ENABLED':'DISABLED'}</div>
                        <div className="font-medium">{feed.name}</div>
                        <div className="text-xs text-slate-500">{feed.url}</div>
                      </div>
                      <div className="text-sm text-slate-600 mt-2">Interval: {feed.interval} min · Last check: {feed.lastChecked || '—'} · Status: {feed.lastStatus || '—'}</div>
                    </div>
                    <div className="flex flex-col gap-2 ml-4">
                      <button onClick={()=>openEdit(feed)} className="px-2 py-1 border rounded">Edit</button>
                      <button onClick={()=>triggerCheck(feed.id)} className="px-2 py-1 bg-amber-500 text-white rounded">Check</button>
                      <button onClick={()=>openLogs(feed.id)} className="px-2 py-1 border rounded">Logs</button>
                      <button onClick={()=>removeFeed(feed.id)} className="px-2 py-1 bg-red-600 text-white rounded">Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded shadow p-4 mt-4">
            <h2 className="font-semibold mb-2">Recent Activity</h2>
            <div className="text-sm text-slate-600">List of recent events will be shown here (backend should supply aggregated events endpoint if desired).</div>
          </div>
        </div>

        <aside className="bg-white rounded shadow p-4">
          <h3 className="font-semibold mb-2">Transmission Settings</h3>
          <label className="block text-sm">RPC URL</label>
          <input className="w-full border rounded px-2 py-1 mb-2" value={transSettings.rpcUrl} onChange={e=>setTransSettings({...transSettings, rpcUrl: e.target.value})} placeholder="http://192.168.2.104:9091/transmission/rpc" />
          <label className="block text-sm">Download directory</label>
          <input className="w-full border rounded px-2 py-1 mb-2" value={transSettings.downloadDir} onChange={e=>setTransSettings({...transSettings, downloadDir: e.target.value})} />
          <div className="flex gap-2 mt-2">
            <button onClick={saveTransSettings} className="px-3 py-1 bg-sky-600 text-white rounded">Save</button>
            <button onClick={()=>{ localStorage.removeItem('tr_settings'); setTransSettings({rpcUrl:'',downloadDir:'/data'}); showToast('Cleared','info'); }} className="px-3 py-1 border rounded">Clear</button>
          </div>
          <div className="mt-4 text-sm text-slate-600">Transmission settings are stored locally in your browser. The backend can also be configured to use these values when sending jobs.</div>
        </aside>
      </section>

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
          <form onSubmit={submitForm} className="bg-white rounded p-6 w-full max-w-md shadow">
            <h3 className="text-lg font-semibold mb-4">{editing? 'Edit Feed':'Add Feed'}</h3>
            <label className="block text-sm mb-1">Name</label>
            <input required className="w-full border rounded px-2 py-1 mb-3" value={form.name} onChange={e=>setForm({...form, name:e.target.value})} />
            <label className="block text-sm mb-1">RSS URL</label>
            <input required className="w-full border rounded px-2 py-1 mb-3" value={form.url} onChange={e=>setForm({...form, url:e.target.value})} />
            <label className="block text-sm mb-1">Interval (minutes)</label>
            <input type="number" min={1} className="w-full border rounded px-2 py-1 mb-3" value={form.interval} onChange={e=>setForm({...form, interval: Number(e.target.value)})} />
            <label className="inline-flex items-center gap-2 mb-3"><input type="checkbox" checked={form.enabled} onChange={e=>setForm({...form, enabled: e.target.checked})} /> Enabled</label>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={()=>setShowForm(false)} className="px-3 py-1 border rounded">Cancel</button>
              <button type="submit" className="px-3 py-1 bg-sky-600 text-white rounded">Save</button>
            </div>
          </form>
        </div>
      )}

      {/* Logs modal */}
      {logFeed && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-6">
          <div className="bg-white rounded shadow w-full max-w-3xl max-h-[80vh] overflow-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h4 className="font-semibold">Logs for feed {logFeed}</h4>
              <div className="flex gap-2">
                <button onClick={()=>{ setLogFeed(null); setSelectedLogs([]); }} className="px-2 py-1 border rounded">Close</button>
                <button onClick={()=>{ navigator.clipboard.writeText(JSON.stringify(selectedLogs, null, 2)); showToast('Copied logs','success'); }} className="px-2 py-1 border rounded">Copy</button>
              </div>
            </div>
            <div className="p-4 text-sm font-mono">
              {selectedLogs.length===0 && <div className="text-slate-500">No logs</div>}
              {selectedLogs.map((l,idx)=> (
                <div key={idx} className="py-1 border-b">
                  <div className="text-xs text-slate-400">{l.ts}</div>
                  <div className="text-sm">[{l.level}] {l.msg}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed right-6 bottom-6 px-4 py-2 rounded shadow ${toast.type==='error'? 'bg-red-600 text-white' : toast.type==='success'? 'bg-green-600 text-white' : 'bg-slate-800 text-white'}`}>
          {toast.msg}
        </div>
      )}

    </div>
  );
}
