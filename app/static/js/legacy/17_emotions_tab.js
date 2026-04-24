        // --- Emotions Tab ---
        const EMOTIONS_TEST_VOICE = 'EMOTIONS_TEST_VOICE';
        const EMOTIONS_AVAILABLE_VOICES = ["Aiden", "Dylan", "Eric", "Ono_anna", "Ryan", "Serena", "Sohee", "Uncle_fu", "Vivian"];

        let emotionsState = null;
        let emotionsSaveTimer = null;
        let emotionsPollTimer = null;
        let emotionsPlayingSequence = false;

        function emotionsEscapeHtml(value) {
            return String(value || '').replace(/[&<>"']/g, ch => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[ch]));
        }

        function emotionsVoiceType() {
            return document.querySelector('#emotions-voice-card .emotions-voice-type:checked')?.value || 'custom';
        }

        function buildEmotionsVoiceCardHtml(config = {}) {
            const voiceType = config.type || 'custom';
            const refAudio = config.ref_audio || '';
            const selectedClone = refAudio
                ? (window._cloneVoicesCache || []).find(v => refAudio.includes(v.filename))
                : null;
            const selectedDesign = refAudio && !selectedClone
                ? (window._designedVoicesCache || []).find(v => refAudio.includes(v.filename))
                : null;
            const selectedValue = selectedClone
                ? `clone:${selectedClone.id}`
                : selectedDesign
                    ? `design:${selectedDesign.id}`
                    : refAudio ? '__manual__' : '';

            return `
                <div class="border rounded p-2" data-voice="${EMOTIONS_TEST_VOICE}">
                    <div class="d-flex flex-wrap gap-3 mb-2">
                        <label class="form-check-label"><input class="form-check-input emotions-voice-type me-1" type="radio" name="emotions_voice_type" value="custom" ${voiceType === 'custom' ? 'checked' : ''} onchange="emotionsToggleVoiceType()">Custom</label>
                        <label class="form-check-label"><input class="form-check-input emotions-voice-type me-1" type="radio" name="emotions_voice_type" value="builtin_lora" ${voiceType === 'builtin_lora' ? 'checked' : ''} onchange="emotionsToggleVoiceType()">Built-in</label>
                        <label class="form-check-label"><input class="form-check-input emotions-voice-type me-1" type="radio" name="emotions_voice_type" value="clone" ${voiceType === 'clone' ? 'checked' : ''} onchange="emotionsToggleVoiceType()">Clone</label>
                        <label class="form-check-label"><input class="form-check-input emotions-voice-type me-1" type="radio" name="emotions_voice_type" value="lora" ${voiceType === 'lora' ? 'checked' : ''} onchange="emotionsToggleVoiceType()">LoRA</label>
                        <label class="form-check-label"><input class="form-check-input emotions-voice-type me-1" type="radio" name="emotions_voice_type" value="design" ${voiceType === 'design' ? 'checked' : ''} onchange="emotionsToggleVoiceType()">Design</label>
                    </div>
                    <div class="emotions-custom-opts" style="display:${voiceType === 'custom' ? 'block' : 'none'}">
                        <div class="row g-2">
                            <div class="col-md-5">
                                <select class="form-select form-select-sm emotions-voice-select">
                                    ${EMOTIONS_AVAILABLE_VOICES.map(v => `<option value="${v}" ${config.voice === v ? 'selected' : ''}>${v}</option>`).join('')}
                                </select>
                            </div>
                            <div class="col-md-7">
                                <input type="text" class="form-control form-control-sm emotions-character-style" placeholder="Character style" value="${emotionsEscapeHtml(config.character_style || config.default_style || '')}">
                            </div>
                        </div>
                    </div>
                    <div class="emotions-builtin-lora-opts" style="display:${voiceType === 'builtin_lora' ? 'block' : 'none'}">
                        <div class="row g-2">
                            <div class="col-md-5">
                                <select class="form-select form-select-sm emotions-builtin-lora-select">
                                    <option value="">-- Select built-in voice --</option>
                                    ${(window._loraModelsCache || []).filter(m => m.builtin).map(m => `<option value="${m.id}" ${config.adapter_id === m.id ? 'selected' : ''} ${m.downloaded === false ? 'disabled' : ''}>${emotionsEscapeHtml(m.name)}${m.downloaded === false ? ' (not downloaded)' : ''}</option>`).join('')}
                                </select>
                            </div>
                            <div class="col-md-7">
                                <input type="text" class="form-control form-control-sm emotions-builtin-lora-style" placeholder="Character style" value="${voiceType === 'builtin_lora' ? emotionsEscapeHtml(config.character_style || '') : ''}">
                            </div>
                        </div>
                    </div>
                    <div class="emotions-clone-opts" style="display:${voiceType === 'clone' ? 'block' : 'none'}">
                        <div class="input-group input-group-sm mb-2">
                            <select class="form-select emotions-designed-voice-select" onchange="emotionsOnCloneSelect(this)">
                                <option value="">-- Select voice or enter path manually --</option>
                                ${(window._cloneVoicesCache || []).length ? `<optgroup label="Uploaded Voices">${(window._cloneVoicesCache || []).map(v => `<option value="clone:${v.id}" ${selectedValue === `clone:${v.id}` ? 'selected' : ''}>${emotionsEscapeHtml(v.name)}</option>`).join('')}</optgroup>` : ''}
                                ${(window._designedVoicesCache || []).length ? `<optgroup label="Designed Voices">${(window._designedVoicesCache || []).map(v => `<option value="design:${v.id}" ${selectedValue === `design:${v.id}` ? 'selected' : ''}>${emotionsEscapeHtml(v.name)}</option>`).join('')}</optgroup>` : ''}
                                <option value="__manual__" ${selectedValue === '__manual__' ? 'selected' : ''}>Custom path...</option>
                            </select>
                            <button class="btn btn-outline-primary emotions-clone-action-btn" onclick="emotionsCloneAction(this)" title="Upload or download clone"><i class="fas fa-upload"></i> Upload</button>
                            <input type="file" class="emotions-clone-voice-file-input" accept=".wav,.mp3,.flac,.ogg" style="display:none" onchange="emotionsHandleCloneVoiceUpload(this)">
                        </div>
                        <input type="text" class="form-control form-control-sm emotions-ref-text mb-2" placeholder="Reference Text" value="${emotionsEscapeHtml(config.ref_text || '')}">
                        <div class="input-group input-group-sm">
                            <input type="text" class="form-control emotions-ref-audio" placeholder="Path to audio file" value="${emotionsEscapeHtml(refAudio)}" ${selectedClone || selectedDesign ? 'readonly' : ''}>
                            <button class="btn btn-outline-secondary emotions-clone-play-btn" onclick="emotionsPlayCloneVoice(this)" title="Play reference audio" style="display:${refAudio ? 'inline-block' : 'none'}"><i class="fas fa-play"></i></button>
                        </div>
                    </div>
                    <div class="emotions-lora-opts" style="display:${voiceType === 'lora' ? 'block' : 'none'}">
                        <div class="row g-2">
                            <div class="col-md-5">
                                <select class="form-select form-select-sm emotions-lora-adapter-select">
                                    <option value="">-- Select trained adapter --</option>
                                    ${(window._loraModelsCache || []).map(m => `<option value="${m.id}" ${config.adapter_id === m.id ? 'selected' : ''}>${emotionsEscapeHtml(m.name)}</option>`).join('')}
                                </select>
                            </div>
                            <div class="col-md-7">
                                <input type="text" class="form-control form-control-sm emotions-lora-character-style" placeholder="Character style" value="${voiceType === 'lora' ? emotionsEscapeHtml(config.character_style || '') : ''}">
                            </div>
                        </div>
                    </div>
                    <div class="emotions-design-opts" style="display:${voiceType === 'design' ? 'block' : 'none'}">
                        <input type="text" class="form-control form-control-sm emotions-design-description mb-2" placeholder="Base voice description" value="${emotionsEscapeHtml(config.description || '')}">
                        <input type="text" class="form-control form-control-sm emotions-design-sample-text" placeholder="Sample text for this designed voice" value="${emotionsEscapeHtml(config.ref_text || '')}">
                    </div>
                </div>
            `;
        }

        function collectEmotionsVoiceConfig() {
            const card = document.getElementById('emotions-voice-card');
            const type = emotionsVoiceType();
            const base = { type, seed: '-1' };
            if (type === 'custom') {
                return {
                    ...base,
                    voice: card.querySelector('.emotions-voice-select')?.value || 'Ryan',
                    character_style: card.querySelector('.emotions-character-style')?.value || '',
                };
            }
            if (type === 'clone') {
                return {
                    ...base,
                    ref_text: card.querySelector('.emotions-ref-text')?.value || '',
                    ref_audio: card.querySelector('.emotions-ref-audio')?.value || '',
                    generated_ref_text: '',
                };
            }
            if (type === 'builtin_lora') {
                const adapterId = card.querySelector('.emotions-builtin-lora-select')?.value || '';
                const adapterEntry = (window._loraModelsCache || []).find(m => m.id === adapterId);
                return {
                    ...base,
                    adapter_id: adapterId,
                    adapter_path: adapterEntry?.adapter_path || '',
                    character_style: card.querySelector('.emotions-builtin-lora-style')?.value || '',
                };
            }
            if (type === 'lora') {
                const adapterId = card.querySelector('.emotions-lora-adapter-select')?.value || '';
                const adapterEntry = (window._loraModelsCache || []).find(m => m.id === adapterId);
                return {
                    ...base,
                    adapter_id: adapterId,
                    adapter_path: adapterEntry?.adapter_path || (adapterId ? `lora_models/${adapterId}` : ''),
                    character_style: card.querySelector('.emotions-lora-character-style')?.value || '',
                };
            }
            return {
                ...base,
                description: card.querySelector('.emotions-design-description')?.value || '',
                ref_text: card.querySelector('.emotions-design-sample-text')?.value || '',
                ref_audio: '',
                generated_ref_text: '',
            };
        }

        async function saveEmotionsConfigNow() {
            const text = document.getElementById('emotions-text')?.value || '';
            const voice_config = collectEmotionsVoiceConfig();
            await API.post('/api/emotions/config', { text, voice_config });
        }

        function debouncedSaveEmotionsConfig() {
            clearTimeout(emotionsSaveTimer);
            emotionsSaveTimer = setTimeout(() => {
                saveEmotionsConfigNow().catch(e => showToast(`Failed to save Emotions config: ${e.message}`, 'error'));
            }, 500);
        }

        window.emotionsToggleVoiceType = () => {
            const type = emotionsVoiceType();
            document.querySelector('#emotions-voice-card .emotions-custom-opts').style.display = type === 'custom' ? 'block' : 'none';
            document.querySelector('#emotions-voice-card .emotions-builtin-lora-opts').style.display = type === 'builtin_lora' ? 'block' : 'none';
            document.querySelector('#emotions-voice-card .emotions-clone-opts').style.display = type === 'clone' ? 'block' : 'none';
            document.querySelector('#emotions-voice-card .emotions-lora-opts').style.display = type === 'lora' ? 'block' : 'none';
            document.querySelector('#emotions-voice-card .emotions-design-opts').style.display = type === 'design' ? 'block' : 'none';
            debouncedSaveEmotionsConfig();
        };

        function emotionsUpdateCloneActionButton() {
            const btn = document.querySelector('#emotions-voice-card .emotions-clone-action-btn');
            const select = document.querySelector('#emotions-voice-card .emotions-designed-voice-select');
            if (!btn || !select) return;
            if (String(select.value || '').startsWith('clone:')) {
                btn.dataset.cloneAction = 'download';
                btn.innerHTML = '<i class="fas fa-download"></i> Download';
                btn.title = 'Download selected clone voice';
            } else {
                btn.dataset.cloneAction = 'upload';
                btn.innerHTML = '<i class="fas fa-upload"></i> Upload';
                btn.title = 'Upload audio file';
            }
        }

        window.emotionsOnCloneSelect = (select) => {
            const card = document.getElementById('emotions-voice-card');
            const refText = card.querySelector('.emotions-ref-text');
            const refAudio = card.querySelector('.emotions-ref-audio');
            const playBtn = card.querySelector('.emotions-clone-play-btn');
            const val = select.value;
            if (!val || val === '__manual__') {
                refAudio.readOnly = false;
                if (val === '__manual__') {
                    refText.value = '';
                    refAudio.value = '';
                    refAudio.focus();
                }
                if (playBtn) playBtn.style.display = 'none';
                emotionsUpdateCloneActionButton();
                debouncedSaveEmotionsConfig();
                return;
            }
            if (val.startsWith('clone:')) {
                const voice = (window._cloneVoicesCache || []).find(v => v.id === val.substring(6));
                if (voice) {
                    refAudio.value = `clone_voices/${voice.filename}`;
                    refText.value = voice.sample_text || '';
                    refAudio.readOnly = true;
                    if (playBtn) playBtn.style.display = 'inline-block';
                }
            } else if (val.startsWith('design:')) {
                const voice = (window._designedVoicesCache || []).find(v => v.id === val.substring(7));
                if (voice) {
                    refAudio.value = `designed_voices/${voice.filename}`;
                    refText.value = voice.sample_text || '';
                    refAudio.readOnly = true;
                    if (playBtn) playBtn.style.display = 'inline-block';
                }
            }
            emotionsUpdateCloneActionButton();
            debouncedSaveEmotionsConfig();
        };

        window.emotionsCloneAction = (btn) => {
            if ((btn.dataset.cloneAction || 'upload') === 'download') {
                const select = document.querySelector('#emotions-voice-card .emotions-designed-voice-select');
                const value = String(select?.value || '');
                if (!value.startsWith('clone:')) return;
                const voiceId = value.substring(6);
                const endpoint = `/api/clone_voices/${encodeURIComponent(voiceId)}/download?speaker=${encodeURIComponent(EMOTIONS_TEST_VOICE)}&ref_text=${encodeURIComponent(document.querySelector('#emotions-voice-card .emotions-ref-text')?.value || '')}`;
                window.location.href = endpoint;
                return;
            }
            document.querySelector('#emotions-voice-card .emotions-clone-voice-file-input')?.click();
        };

        window.emotionsHandleCloneVoiceUpload = async (input) => {
            const file = input.files?.[0];
            if (!file) return;
            input.value = '';
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch('/api/clone_voices/upload', { method: 'POST', body: formData });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
                    showToast(err.detail || 'Upload failed', 'error');
                    return;
                }
                const result = await res.json();
                window._cloneVoicesCache = await API.get('/api/clone_voices/list');
                const uploaded = (window._cloneVoicesCache || []).find(v => v.id === result.voice_id) || result;
                const select = document.querySelector('#emotions-voice-card .emotions-designed-voice-select');
                if (select && uploaded?.voice_id && !uploaded.id) uploaded.id = uploaded.voice_id;
                if (select && uploaded?.id) {
                    let option = Array.from(select.options).find(o => o.value === `clone:${uploaded.id}`);
                    if (!option) {
                        option = new Option(uploaded.name || file.name.replace(/\.[^.]+$/, ''), `clone:${uploaded.id}`);
                        select.add(option);
                    }
                    select.value = `clone:${uploaded.id}`;
                    emotionsOnCloneSelect(select);
                }
                showToast(`Uploaded "${file.name}"`, 'success');
            } catch (e) {
                showToast(`Upload failed: ${e.message}`, 'error');
            }
        };

        window.emotionsPlayCloneVoice = (btn) => {
            const refAudio = document.querySelector('#emotions-voice-card .emotions-ref-audio')?.value || '';
            if (!refAudio) return;
            playSharedPreviewAudio(`/${refAudio}?t=${Date.now()}`).catch(e => {
                if (isPreviewAbortError(e)) return;
                showToast(`Preview playback failed: ${e.message}`, 'error');
            });
        };

        function buildEmotionsRowHtml(row) {
            const status = row.status || 'pending';
            const statusColor = status === 'done' ? 'success' : status === 'generating' ? 'warning' : status === 'error' ? 'danger' : 'secondary';
            const audioHtml = row.audio_url
                ? `<button type="button" class="btn btn-outline-secondary btn-sm emotions-audio-toggle" onclick="emotionsToggleAudio(this)" aria-label="Play audio" title="Play audio"><i class="fas fa-play"></i></button><audio class="emotions-audio" data-index="${row.index}" preload="none" src="${emotionsEscapeHtml(row.audio_url)}" style="display:none;"></audio>`
                : `<button class="btn btn-primary btn-sm" onclick="emotionsRenderRow(${row.index})"><i class="fas fa-play me-1"></i>Render</button>`;
            return `
                <tr data-emotions-index="${row.index}" class="${status === 'done' ? 'status-done' : status === 'generating' ? 'status-generating' : ''}">
                    <td class="text-center text-muted">${Number(row.index) + 1}</td>
                    <td>${emotionsEscapeHtml(row.instruct)}</td>
                    <td><span class="badge bg-${statusColor}">${emotionsEscapeHtml(status)}</span>${row.error ? `<div class="small text-danger mt-1">${emotionsEscapeHtml(row.error)}</div>` : ''}</td>
                    <td><div class="d-flex align-items-center gap-2">${audioHtml}</div></td>
                </tr>
            `;
        }

        function renderEmotionsRows(rows) {
            const body = document.getElementById('emotions-table-body');
            if (!body) return;
            body.innerHTML = (rows || []).map(row => buildEmotionsRowHtml(row)).join('');
            updateEmotionsProgress(rows || []);
        }

        function updateEmotionsProgress(rows) {
            const bar = document.getElementById('emotions-progress-bar');
            if (!bar) return;
            const done = (rows || []).filter(row => row.status === 'done').length;
            const total = (rows || []).length || 20;
            const pct = total > 0 ? Math.round((done / total) * 100) : 0;
            bar.style.width = `${pct}%`;
            bar.innerText = `${pct}% (${done}/${total})`;
        }

        async function loadEmotionsVoiceCaches() {
            try { window._designedVoicesCache = await API.get('/api/voice_design/list'); } catch (_e) {}
            try { window._cloneVoicesCache = await API.get('/api/clone_voices/list'); } catch (_e) {}
            try { window._loraModelsCache = await API.get('/api/lora/models'); } catch (_e) {}
        }

        window.loadEmotions = async () => {
            await loadEmotionsVoiceCaches();
            emotionsState = await API.get('/api/emotions');
            const textInput = document.getElementById('emotions-text');
            if (textInput && textInput.dataset.bound !== '1') {
                textInput.dataset.bound = '1';
                textInput.addEventListener('input', debouncedSaveEmotionsConfig);
                textInput.addEventListener('change', debouncedSaveEmotionsConfig);
            }
            if (textInput) textInput.value = emotionsState.text || '';
            const voiceCard = document.getElementById('emotions-voice-card');
            if (voiceCard) {
                voiceCard.innerHTML = buildEmotionsVoiceCardHtml(emotionsState.voice_config || {});
                voiceCard.querySelectorAll('input, select').forEach(el => {
                    el.addEventListener('input', debouncedSaveEmotionsConfig);
                    el.addEventListener('change', debouncedSaveEmotionsConfig);
                });
                emotionsUpdateCloneActionButton();
            }
            renderEmotionsRows(emotionsState.rows || []);
            await emotionsPollStatus(true);
        };

        window.emotionsRenderRow = async (index) => {
            await saveEmotionsConfigNow();
            const row = document.querySelector(`#emotions-table-body tr[data-emotions-index="${index}"]`);
            if (row) {
                const status = row.querySelector('td:nth-child(3)');
                if (status) status.innerHTML = '<span class="badge bg-warning">generating</span>';
            }
            try {
                const result = await API.post(`/api/emotions/render/${encodeURIComponent(index)}`, {});
                if (emotionsState?.rows?.[index]) emotionsState.rows[index] = result;
                renderEmotionsRows(emotionsState?.rows || []);
            } catch (e) {
                showToast(`Emotion render failed: ${e.message}`, 'error');
                await loadEmotions();
            }
        };

        window.emotionsRender = async (regenerateAll = false) => {
            await saveEmotionsConfigNow();
            try {
                const result = await API.post('/api/emotions/render', { regenerate_all: !!regenerateAll });
                if (result.status === 'idle') {
                    showToast('All emotion clips are already generated.', 'warning');
                    return;
                }
                document.getElementById('emotions-btn-render').style.display = 'none';
                document.getElementById('emotions-btn-regen').style.display = 'none';
                document.getElementById('emotions-btn-cancel').style.display = '';
                emotionsStartPolling();
                showToast(`Queued ${result.total} emotion clip${result.total === 1 ? '' : 's'}.`, 'success');
            } catch (e) {
                showToast(`Emotions render failed: ${e.message}`, 'error');
            }
        };

        window.emotionsCancel = async () => {
            try {
                await API.post('/api/emotions/cancel', {});
            } catch (e) {
                console.error('Emotions cancel failed', e);
            }
            emotionsStartPolling();
        };

        function emotionsStartPolling() {
            if (emotionsPollTimer) clearInterval(emotionsPollTimer);
            emotionsPollTimer = setInterval(() => emotionsPollStatus(false), 1500);
            emotionsPollStatus(false).catch(() => {});
        }

        async function emotionsPollStatus(silent = false) {
            try {
                const status = await API.get('/api/emotions/status');
                if (status.rows) {
                    if (!emotionsState) emotionsState = {};
                    emotionsState.rows = status.rows;
                    renderEmotionsRows(status.rows);
                }
                const logsEl = document.getElementById('emotions-logs');
                if (logsEl && status.logs && status.logs.length) {
                    logsEl.style.display = '';
                    logsEl.innerText = status.logs.join('\n');
                    logsEl.scrollTop = logsEl.scrollHeight;
                }
                const running = !!status.running;
                document.getElementById('emotions-btn-render').style.display = running ? 'none' : '';
                document.getElementById('emotions-btn-regen').style.display = running ? 'none' : '';
                document.getElementById('emotions-btn-cancel').style.display = running ? '' : 'none';
                if (!running && emotionsPollTimer) {
                    clearInterval(emotionsPollTimer);
                    emotionsPollTimer = null;
                    if (!silent) {
                        await loadEmotions();
                    }
                }
            } catch (e) {
                if (!silent) console.error('Emotions status poll failed', e);
            }
        }

        window.emotionsToggleAudio = async (button) => {
            const audio = button?.parentElement?.querySelector('audio.emotions-audio');
            if (!audio) return;
            try {
                if (!audio.paused && !audio.ended) {
                    audio.pause();
                    button.innerHTML = '<i class="fas fa-play"></i>';
                    return;
                }
                document.querySelectorAll('audio.emotions-audio').forEach(other => {
                    if (other !== audio) other.pause();
                });
                audio.currentTime = 0;
                button.innerHTML = '<i class="fas fa-pause"></i>';
                audio.onended = () => { button.innerHTML = '<i class="fas fa-play"></i>'; };
                audio.onpause = () => { button.innerHTML = '<i class="fas fa-play"></i>'; };
                await audio.play();
            } catch (e) {
                button.innerHTML = '<i class="fas fa-play"></i>';
                showToast(`Playback failed: ${e.message}`, 'error');
            }
        };

        window.emotionsPlaySequence = async () => {
            if (emotionsPlayingSequence) {
                emotionsPlayingSequence = false;
                return;
            }
            emotionsPlayingSequence = true;
            const audios = Array.from(document.querySelectorAll('audio.emotions-audio'));
            for (const audio of audios) {
                if (!emotionsPlayingSequence) break;
                try {
                    audio.currentTime = 0;
                    await audio.play();
                    await new Promise(resolve => {
                        audio.onended = resolve;
                        audio.onerror = resolve;
                    });
                } catch (_e) {
                    // Skip clips the browser refuses to play.
                }
            }
            emotionsPlayingSequence = false;
        };
