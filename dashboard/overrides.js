// Compatibility overrides for the redesigned dashboard shell.
async function loadOverview(){
  try{
    const [o,ideas]=await Promise.all([request('/overview'),request('/ideas?limit=10')]);
    const map={
      'o-research':o.research_items,'o-ideas':o.ideas,'o-approved':o.approved,'o-published':o.published,
      'p-research':o.research_items,'p-ideas':o.ideas,'p-review':o.review,'p-scripts':o.scripts,
      'p-production':o.production,'p-published':o.published
    };
    Object.entries(map).forEach(([id,value])=>{if($(id))$(id).textContent=value??0});
    $('overview-table').innerHTML=ideas.length?ideas.map(i=>`<tr><td>${esc(i.title)}</td><td>${esc(i.topic)}</td><td class="score">${i.overall_score??'—'}</td><td><span class="badge">${esc(i.status)}</span></td></tr>`).join(''):'<tr><td colspan="4" class="muted">No ideas yet. Run Research to populate the pipeline.</td></tr>';
    $('system').textContent='● System healthy';$('system').className='status good';
  }catch(e){$('system').textContent='● API offline';$('system').className='status bad';console.error(e)}
}
function showResearch(){document.getElementById('research').classList.add('active')}
async function runResearch(){
  const b=$('research-run'),msg=$('research-msg');b.disabled=true;b.textContent='Researching…';msg.textContent='';
  try{
    const channels=$('channels').value.split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);
    if(!channels.length)throw Error('Enter at least one YouTube channel.');
    const resolved=await rootRequest('/api/research/youtube/resolve',{method:'POST',body:JSON.stringify({channel_ids:channels})});
    $('resolved').innerHTML=[...resolved.resolved.map(x=>`<span class="chip good">✓ ${esc(x.input)}<small>${esc(x.channel_id)}</small></span>`),...resolved.failed.map(x=>`<span class="chip bad">✕ ${esc(x.input)}<small>${esc(x.error)}</small></span>`)].join('');
    if(!resolved.resolved.length)throw Error('No channels could be resolved.');
    if(resolved.failed.length)throw Error('Could not resolve: '+resolved.failed.map(x=>x.input).join(', '));
    const r=await rootRequest('/api/research/youtube',{method:'POST',body:JSON.stringify({channel_ids:resolved.resolved.map(x=>x.channel_id),query:$('query').value.trim(),limit:Number($('limit').value)||20,generate_ideas:true})});
    msg.innerHTML=`<span class="success">Found ${r.research_items_found} research items and created ${r.ideas_created} ideas.</span>`;
    $('research-results').innerHTML=r.research.length?r.research.map(x=>`<div class="item"><strong>${esc(x.title)}</strong><div class="muted">${esc(x.source_name||'YouTube')} · ${esc(x.published_at||'')}</div><p>${esc(x.summary)}</p>${x.url?`<a class="link" href="${esc(x.url)}" target="_blank" rel="noreferrer">Open source</a>`:''}</div>`).join(''):'<div class="empty">No results.</div>';
    $('research-ideas').innerHTML=r.ideas.length?r.ideas.map(ideaCard).join(''):'<div class="empty">No ideas generated.</div>';
    await loadOverview();
  }catch(e){msg.innerHTML=`<span class="error">${esc(e.message)}</span>`}finally{b.disabled=false;b.textContent='Run Research'}
}
async function setIdeaStatus(id,status){try{await rootRequest('/api/dashboard/ideas/'+encodeURIComponent(id)+'/status',{method:'PATCH',body:JSON.stringify({status})});if(document.getElementById('ideas').classList.contains('active'))await loadIdeas();if(document.getElementById('review').classList.contains('active'))await loadReview();await loadOverview()}catch(e){alert('Status update failed: '+e.message)}}
