/* Production workflow controls for the operator dashboard. */

function productionAction(label, fn, cls = 'secondary') {
    return button(label, fn, cls);
}

function productionActions(job) {
    if (job.status === 'QUEUED') {
        return productionAction('Prepare Assets', `setProduction('${job.production_id}','ASSETS')`, 'primary');
    }

    if (job.status === 'ASSETS') {
        return productionAction('Start Rendering', `setProduction('${job.production_id}','RENDERING')`, 'primary');
    }

    if (job.status === 'RENDERING') {
        return `
            <div class="production-artifact">
                <input id="artifact-${esc(job.production_id)}" placeholder="Artifact URI / MP4 path">
                ${productionAction('Register Artifact', `registerArtifact('${job.production_id}')`, 'primary')}
            </div>
            ${productionAction('Mark Failed', `setProduction('${job.production_id}','FAILED')`, 'danger')}
        `;
    }

    if (job.status === 'READY') {
        return productionAction('Open Publishing', `show('publishing')`, 'primary');
    }

    return '<span class="muted">Production stopped. No retry action is available yet.</span>';
}

async function showProduction() {
    document.getElementById('production').classList.add('active');
    try {
        const data = await request('/production');
        $('production-list').innerHTML = data.length
            ? data.map(x => `
                <div class="row-card production-card">
                    <div>
                        <strong>${esc(x.production_id)}</strong>
                        <div class="muted">Script: ${esc(x.script_id)}</div>
                        ${x.output_path ? `<div class="muted">Artifact: ${esc(x.output_path)}</div>` : ''}
                        ${x.error ? `<div class="error">${esc(x.error)}</div>` : ''}
                    </div>
                    <span class="badge">${esc(x.status)}</span>
                    <div class="mini-actions production-actions">${productionActions(x)}</div>
                </div>
            `).join('')
            : '<div class="empty">No production jobs.</div>';
    } catch (e) {
        $('production-list').innerHTML = `<div class="error">${esc(e.message)}</div>`;
    }
}

async function setProduction(id, status) {
    try {
        await request(`/production/${encodeURIComponent(id)}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status })
        });
        await showProduction();
    } catch (e) {
        alert(e.message);
    }
}

async function registerArtifact(id) {
    const input = $(`artifact-${id}`);
    const artifactUri = input ? input.value.trim() : '';

    if (!artifactUri) {
        alert('Enter the artifact URI or MP4 path first.');
        return;
    }

    try {
        await request(`/production/${encodeURIComponent(id)}/artifact`, {
            method: 'POST',
            body: JSON.stringify({ artifact_uri: artifactUri })
        });
        await request(`/production/${encodeURIComponent(id)}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status: 'READY' })
        });
        await showProduction();
    } catch (e) {
        alert(e.message);
    }
}
