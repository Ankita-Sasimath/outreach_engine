const $ = (id) => document.getElementById(id);

function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '<')
    .replaceAll('>', '>')
    .replaceAll('"', '"')
    .replaceAll("'", '&#039;');
}

function addProgressItem({stage, message, progress, total}){
  const li = document.createElement('li');
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = message + (total ? ` (total: ${total})` : '');
  const right = document.createElement('div');
  right.textContent = progress ? `${progress}%` : '';
  li.appendChild(meta);
  li.appendChild(right);
  li.dataset.stage = stage;
  $('progressList').appendChild(li);
}

function finishPipeline({es, finishedRef, showError = false, message = ''}){
  if(finishedRef) finishedRef.value = true;
  if(es) es.close();
  $('startBtn').disabled = false;
  $('startBtn').textContent = 'Start Pipeline';
  if(showError){
    $('error').style.display = 'block';
    $('error').textContent = message;
  }
}

function clearUI(){
  $('error').style.display = 'none';
  $('error').textContent = '';
  $('progressList').innerHTML = '';
  $('companiesFound').textContent = '0';
  $('contactsFound').textContent = '0';
  $('emailsResolved').textContent = '0';
  $('emailsReady').textContent = '0';
  $('confirmPanel').style.display = 'none';
  $('previewPanel').style.display = 'none';
  $('previews').innerHTML = '';
  $('sentCount').textContent = '0';
  $('skippedCount').textContent = '0';
}

async function apiPost(url, body){
  const res = await fetch(url, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)
  });
  if(!res.ok){
    const t = await res.text();
    throw new Error(`HTTP ${res.status}: ${t}`);
  }
  return res.json();
}

$('startBtn').addEventListener('click', async () => {
  clearUI();
  const domain = $('domain').value.trim().toLowerCase();
  if(!domain){
    $('error').style.display = 'block';
    $('error').textContent = 'Enter a valid company domain.';
    return;
  }

  $('startBtn').disabled = true;
  $('startBtn').textContent = 'Running...';

  let es = null;
  const finishedRef = { value: false };

  try{
    const data = await apiPost('/api/pipeline/run', {domain});

    $('confirmCount').textContent = data.emails_ready ?? 0;

    // Polling-based SSE stream
    es = new EventSource(`/api/pipeline/${data.run_id}/events`);

    const stageMap = new Map();

    es.onmessage = (evt) => {
      const payload = JSON.parse(evt.data);
      if(payload.type === 'error'){
        finishPipeline({
          es,
          finishedRef,
          showError: true,
          message: payload.message || 'Pipeline run not found.',
        });
        return;
      }
      if(payload.type !== 'snapshot') return;

      $('companiesFound').textContent = payload.companies_found ?? 0;
      $('contactsFound').textContent = payload.contacts_found ?? 0;
      $('emailsResolved').textContent = payload.emails_resolved ?? 0;
      $('emailsReady').textContent = payload.emails_ready ?? 0;

      // render only new activity items
      const activity = payload.new_activity || [];
      for(const a of activity){
        const key = a.stage + '|' + a.message;
        if(stageMap.has(key)) continue;
        stageMap.set(key, true);

        const prefix = a.stage === 'failed' ? '✗ ' : '✓ ';
        addProgressItem({
          stage: a.stage,
          message: `${prefix}${a.message}`,
          progress: a.progress ?? 0,
          total: a.total ?? null
        });
      }

      if(payload.status === 'completed'){
        $('confirmCount').textContent = payload.emails_ready ?? 0;
        $('confirmPanel').style.display = (payload.emails_ready > 0) ? 'block' : 'none';
        finishPipeline({ es, finishedRef });
      }

      if(payload.status === 'failed'){
        const failedActivity = [...activity].reverse().find((a) => a.stage === 'failed');
        finishPipeline({
          es,
          finishedRef,
          showError: true,
          message: failedActivity?.message || 'Pipeline failed.',
        });
      }
    };

    es.onerror = () => {
      if(finishedRef.value) return;
      finishPipeline({
        es,
        finishedRef,
        showError: true,
        message: 'Lost connection to the server while the pipeline was running.',
      });
    };

  }catch(e){
    $('error').style.display = 'block';
    $('error').textContent = e.message;
    finishPipeline({ es, finishedRef });
  }
});


$('sendBtn').addEventListener('click', async () => {
  const domain = $('domain').value.trim().toLowerCase();
  $('sendBtn').disabled = true;
  $('sendBtn').textContent = 'Sending...';

  try{
    const data = await apiPost('/api/pipeline/confirm-send', {domain, send:true});
    $('previewPanel').style.display = 'block';
    $('sentCount').textContent = data.sent ?? 0;
    $('skippedCount').textContent = data.skipped ?? 0;

    const previews = data.previews || [];
    $('previews').innerHTML = '';
    for(const p of previews){
      const div = document.createElement('div');
      div.className = 'preview';
      div.innerHTML = `
        <div class="to">To: ${escapeHtml(p.to_email)}</div>
        <div class="subj">${escapeHtml(p.subject)}</div>
        <pre>${escapeHtml(p.body)}</pre>
      `;
      $('previews').appendChild(div);
    }
  }catch(e){
    $('error').style.display = 'block';
    $('error').textContent = e.message;
  }finally{
    $('sendBtn').disabled = false;
    $('sendBtn').textContent = 'Send Emails';
  }
});

