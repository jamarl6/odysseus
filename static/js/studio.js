/**
 * Studio Module — Photo and Video processing.
 */

import uiModule from './ui.js';
import * as Modals from './modalManager.js';
import { makeWindowDraggable } from './windowDrag.js';

let _open = false;
let _media = [];
let _pollingIntervals = {};

export function toggleStudioPanel() {
  if (_open) {
    closeStudioPanel();
  } else {
    openStudioPanel();
  }
}

function openStudioPanel() {
  if (_open) return;
  _open = true;
  document.getElementById('tool-studio-btn')?.classList.add('active');
  
  let pane = document.getElementById('studio-pane');
  if (!pane) {
    pane = document.createElement('div');
    pane.id = 'studio-pane';
    pane.className = 'modal-window admin-modal';
    pane.style.width = '800px';
    pane.style.height = '600px';
    pane.style.left = 'calc(50vw - 400px)';
    pane.style.top = '100px';
    pane.style.zIndex = 1000;
    
    pane.innerHTML = `
      <div class="modal-header">
        <div class="modal-title">Media Studio</div>
        <div class="modal-actions">
          <button class="btn btn-sm" id="studio-gen-photo-btn">Generate Photo</button>
          <button class="btn btn-sm" id="studio-gen-video-btn">Generate Video</button>
          <button class="close-btn" id="studio-close-btn">✕</button>
        </div>
      </div>
      <div class="modal-content" style="padding:0; display:flex; flex-direction:column; height:calc(100% - 45px); background:var(--bg-card);">
        
        <!-- Generate Photo Modal (Inline) -->
        <div id="studio-photo-modal" style="display:none; padding:15px; border-bottom:1px solid var(--border);">
          <h4>Generate Photo</h4>
          <textarea id="studio-photo-prompt" class="chat-input" placeholder="Enter photo prompt..."></textarea>
          <input type="text" id="studio-photo-model-override" class="settings-input" placeholder="Override Model ID (Optional)" style="margin-top:10px;" />
          <div style="margin-top:10px;">
            <button class="btn btn-primary" id="studio-do-gen-photo">Generate</button>
            <button class="btn" id="studio-cancel-photo">Cancel</button>
          </div>
          <div id="studio-photo-status" style="margin-top:5px; font-size:12px; color:var(--text-muted);"></div>
        </div>

        <!-- Generate Video Modal (Inline) -->
        <div id="studio-video-modal" style="display:none; padding:15px; border-bottom:1px solid var(--border);">
          <h4>Generate Video</h4>
          <textarea id="studio-video-prompt" class="chat-input" placeholder="Enter video prompt..."></textarea>
          <input type="text" id="studio-video-model-override" class="settings-input" placeholder="Override Model ID (Optional)" style="margin-top:10px;" />
          <div style="margin-top:10px;">
            <button class="btn btn-primary" id="studio-do-gen-video">Generate</button>
            <button class="btn" id="studio-cancel-video">Cancel</button>
          </div>
          <div id="studio-video-status" style="margin-top:5px; font-size:12px; color:var(--text-muted);"></div>
        </div>

        <div id="studio-grid" style="flex:1; overflow-y:auto; padding:15px; display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:15px;">
        </div>
      </div>
    `;
    document.body.appendChild(pane);
    
    makeWindowDraggable(pane, {
      header: pane.querySelector('.modal-header'),
      content: pane.querySelector('.modal-content'),
      enableDock: true
    });

    pane.querySelector('#studio-close-btn').addEventListener('click', closeStudioPanel);
    
    // Gen Photo
    pane.querySelector('#studio-gen-photo-btn').addEventListener('click', () => {
      document.getElementById('studio-photo-modal').style.display = 'block';
      document.getElementById('studio-video-modal').style.display = 'none';
    });
    pane.querySelector('#studio-cancel-photo').addEventListener('click', () => {
      document.getElementById('studio-photo-modal').style.display = 'none';
    });
    pane.querySelector('#studio-do-gen-photo').addEventListener('click', generatePhoto);
    
    // Gen Video
    pane.querySelector('#studio-gen-video-btn').addEventListener('click', () => {
      document.getElementById('studio-video-modal').style.display = 'block';
      document.getElementById('studio-photo-modal').style.display = 'none';
    });
    pane.querySelector('#studio-cancel-video').addEventListener('click', () => {
      document.getElementById('studio-video-modal').style.display = 'none';
    });
    pane.querySelector('#studio-do-gen-video').addEventListener('click', generateVideo);
    
    Modals.register('studio-panel', {
      railBtnId: 'tool-studio-btn',
      closeFn: closeStudioPanel,
    });
  } else {
    pane.classList.remove('hidden');
    pane.style.display = 'block';
  }

  loadLibrary();
}

function closeStudioPanel() {
  _open = false;
  document.getElementById('tool-studio-btn')?.classList.remove('active');
  const pane = document.getElementById('studio-pane');
  if (pane) {
    pane.classList.add('hidden');
    pane.style.display = 'none';
  }
}

async function loadLibrary() {
  try {
    const res = await fetch('/api/studio/library');
    const data = await res.json();
    _media = data.media || [];
    renderGrid();
    
    // Resume polling for pending videos
    _media.forEach(m => {
      if (m.media_type === 'video' && m.job_status === 'pending') {
        startPolling(m.id);
      }
    });
  } catch (err) {
    console.error("Failed to load studio library:", err);
  }
}

function renderGrid() {
  const grid = document.getElementById('studio-grid');
  if (!grid) return;
  grid.innerHTML = '';
  
  if (_media.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; color:var(--text-muted); margin-top:50px;">No media found. Generate a photo or video to get started!</div>';
    return;
  }

  _media.forEach(m => {
    const card = document.createElement('div');
    card.style.cssText = 'position:relative; background:var(--bg); border:1px solid var(--border); border-radius:8px; overflow:hidden; aspect-ratio:1; display:flex; align-items:center; justify-content:center; flex-direction:column;';
    
    if (m.media_type === 'photo') {
      card.innerHTML = `<img src="${m.url}" style="width:100%; height:100%; object-fit:cover;" />`;
    } else if (m.media_type === 'video') {
      if (m.job_status === 'pending') {
        card.innerHTML = `<div style="padding:20px; text-align:center; font-size:12px; color:var(--text-muted);">
          <div class="loader" style="margin:0 auto 10px auto;"></div>
          Generating Video...<br/><span style="font-size:10px;">(This can take several minutes)</span>
        </div>`;
      } else if (m.job_status === 'failed') {
        card.innerHTML = `<div style="padding:20px; text-align:center; font-size:12px; color:var(--red);">Video Generation Failed</div>`;
      } else {
        card.innerHTML = `<video src="${m.url}" style="width:100%; height:100%; object-fit:cover;" controls loop></video>`;
      }
    }
    
    // Delete button
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-sm btn-icon';
    delBtn.innerHTML = '✕';
    delBtn.style.cssText = 'position:absolute; top:5px; right:5px; background:rgba(0,0,0,0.5); color:white; border:none; border-radius:50%; width:24px; height:24px; line-height:24px; text-align:center; cursor:pointer; opacity:0; transition:opacity 0.2s;';
    card.addEventListener('mouseenter', () => delBtn.style.opacity = '1');
    card.addEventListener('mouseleave', () => delBtn.style.opacity = '0');
    
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm("Delete this media?")) return;
      try {
        await fetch(`/api/studio/${m.id}`, { method: 'DELETE' });
        loadLibrary();
      } catch (err) {
        console.error("Delete failed", err);
      }
    });
    
    card.appendChild(delBtn);
    grid.appendChild(card);
  });
}

async function generatePhoto() {
  const prompt = document.getElementById('studio-photo-prompt').value.trim();
  const model = document.getElementById('studio-photo-model-override').value.trim();
  const status = document.getElementById('studio-photo-status');
  
  if (!prompt) return;
  
  status.textContent = "Generating...";
  document.getElementById('studio-do-gen-photo').disabled = true;
  
  try {
    const res = await fetch('/api/studio/generate/photo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, model: model || null })
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || err.message || "API Error");
    }
    
    document.getElementById('studio-photo-prompt').value = '';
    document.getElementById('studio-photo-modal').style.display = 'none';
    loadLibrary();
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  } finally {
    document.getElementById('studio-do-gen-photo').disabled = false;
  }
}

async function generateVideo() {
  const prompt = document.getElementById('studio-video-prompt').value.trim();
  const model = document.getElementById('studio-video-model-override').value.trim();
  const status = document.getElementById('studio-video-status');
  
  if (!prompt) return;
  
  status.textContent = "Submitting Video Job...";
  document.getElementById('studio-do-gen-video').disabled = true;
  
  try {
    const res = await fetch('/api/studio/generate/video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, model: model || null })
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || err.message || "API Error");
    }
    
    const media = await res.json();
    document.getElementById('studio-video-prompt').value = '';
    document.getElementById('studio-video-modal').style.display = 'none';
    
    // Add to local state immediately
    _media.unshift(media);
    renderGrid();
    
    if (media.job_status === 'pending') {
      startPolling(media.id);
    }
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  } finally {
    document.getElementById('studio-do-gen-video').disabled = false;
  }
}

function startPolling(mediaId) {
  if (_pollingIntervals[mediaId]) return;
  
  _pollingIntervals[mediaId] = setInterval(async () => {
    try {
      const res = await fetch(`/api/studio/jobs/${mediaId}`);
      if (res.ok) {
        const m = await res.json();
        const idx = _media.findIndex(x => x.id === mediaId);
        if (idx >= 0) {
          _media[idx] = m;
          if (m.job_status === 'completed' || m.job_status === 'failed') {
            clearInterval(_pollingIntervals[mediaId]);
            delete _pollingIntervals[mediaId];
            renderGrid();
          }
        }
      }
    } catch (e) {
      console.warn("Polling error:", e);
    }
  }, 10000); // Poll every 10 seconds
}

// Bind Sidebar button
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('tool-studio-btn');
  if (btn) btn.addEventListener('click', toggleStudioPanel);
});
