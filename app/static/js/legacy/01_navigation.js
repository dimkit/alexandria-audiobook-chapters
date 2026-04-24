        // --- Navigation ---

        const SCRIPT_GATED_TABS = ['voices', 'editor', 'proofread', 'audio'];
        const NAV_TASK_TABS = new Set(['script', 'voices', 'editor', 'proofread', 'audio']);
        let currentNavTaskTab = null;
        let stickyScriptReady = false;

        function renderNavTaskSpinner(tab) {
            currentNavTaskTab = NAV_TASK_TABS.has(tab) ? tab : null;
            document.querySelectorAll('.nav-task-spinner').forEach(el => el.remove());
            if (!currentNavTaskTab) return;
            const link = document.querySelector(`.nav-link[data-tab="${currentNavTaskTab}"]`);
            if (!link) return;
            const spinner = document.createElement('span');
            spinner.className = 'nav-task-spinner';
            spinner.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i><span class="visually-hidden">Working</span>';
            link.appendChild(spinner);
        }

        async function refreshNavTaskSpinner() {
            try {
                const res = await fetch('/api/nav_task');
                if (!res.ok) return;
                const state = await res.json();
                renderNavTaskSpinner(state?.tab || null);
            } catch (e) {
                console.error('Failed to refresh navigation task spinner:', e);
            }
        }

        window.setNavTaskSpinner = async function(tab) {
            if (!NAV_TASK_TABS.has(tab)) return;
            renderNavTaskSpinner(tab);
            try {
                const res = await fetch('/api/nav_task/set', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tab }),
                });
                if (!res.ok) throw new Error(res.statusText);
                const state = await res.json();
                renderNavTaskSpinner(state?.tab || tab);
            } catch (e) {
                console.error('Failed to set navigation task spinner:', e);
            }
        };

        window.releaseNavTaskSpinner = async function(tab = null) {
            if (tab && currentNavTaskTab && tab !== currentNavTaskTab) return;
            if (!tab || tab === currentNavTaskTab) {
                renderNavTaskSpinner(null);
            }
            try {
                const res = await fetch('/api/nav_task/release', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tab }),
                });
                if (!res.ok) throw new Error(res.statusText);
                const state = await res.json();
                renderNavTaskSpinner(state?.tab || null);
            } catch (e) {
                console.error('Failed to release navigation task spinner:', e);
            }
        };
        window.getNavTaskSpinnerTab = () => currentNavTaskTab;
        window.refreshNavTaskSpinner = refreshNavTaskSpinner;

        refreshNavTaskSpinner();

        function updateDictionaryNavVisibility(scriptReady) {
            const dictionaryNavItem = document.getElementById('dictionary-nav-item');
            if (!dictionaryNavItem) return;
            dictionaryNavItem.style.display = scriptReady ? '' : 'none';
        }

        function applyPipelineTabLocks(isLegacy, scriptReady, { persist = true } = {}) {
            if (persist && scriptReady) {
                stickyScriptReady = true;
            }
            const effectiveScriptReady = !!isLegacy || !!scriptReady || stickyScriptReady;
            updateDictionaryNavVisibility(effectiveScriptReady);
            SCRIPT_GATED_TABS.forEach(tab => {
                const link = document.querySelector(`.nav-link[data-tab="${tab}"]`);
                if (!link) return;
                if (effectiveScriptReady) {
                    link.classList.remove('nav-locked');
                } else {
                    link.classList.add('nav-locked');
                }
            });
        }

        window.updatePipelineTabLocks = function(isLegacy, scriptReady) {
            applyPipelineTabLocks(isLegacy, scriptReady);
        };

        window.resetPipelineTabLocks = function() {
            stickyScriptReady = false;
            const isLegacy = !!document.getElementById('legacy-mode-toggle')?.checked;
            applyPipelineTabLocks(isLegacy, false, { persist: false });
        };

        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', async (e) => {
                const target = e.currentTarget;
                if (target.classList.contains('nav-locked')) return;
                const currentTab = document.querySelector('.nav-link.active')?.dataset.tab || null;
                const nextTab = target.dataset.tab;

                if (currentTab === 'editor' && nextTab !== 'editor') {
                    await flushPendingEditorChunkSaves().catch(err => {
                        console.error('Failed to flush editor saves:', err);
                    });
                }
                if (currentTab === 'audio' && nextTab !== 'audio' && window.persistExportConfigFromUI) {
                    await window.persistExportConfigFromUI().catch(err => {
                        console.error('Failed to flush export settings before tab switch:', err);
                    });
                }
                if (currentTab === 'setup' && nextTab !== 'setup' && window.flushSetupConfig) {
                    await window.flushSetupConfig().catch(err => {
                        console.error('Failed to flush setup settings before tab switch:', err);
                    });
                }

                // Remove active class from all links
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                // Add active to clicked
                target.classList.add('active');

                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
                // Show target tab
                const targetId = nextTab + '-tab';
                document.getElementById(targetId).style.display = 'block';

                // Trigger tab specific loads
                if (nextTab === 'editor') {
                    syncEditorChunksOnNavigation()
                        .then((result) => {
                            const needsFullRefresh = !Array.isArray(cachedChunks) || cachedChunks.length === 0 || !!result?.synced;
                            loadChunks(needsFullRefresh);
                        })
                        .catch(err => console.error('Editor sync error', err));
                    refreshAudioQueueUI().catch(err => console.error('Audio queue refresh error', err));
                    ensureAudioQueuePolling();
                    syncNarratorSelectionsFromBackend().catch(() => {});
                } else if (nextTab === 'voices') {
                    loadVoices();
                } else if (nextTab === 'dictionary') {
                    loadDictionary();
                } else if (nextTab === 'saved-scripts') {
                    loadSavedScripts();
                } else if (nextTab === 'emotions') {
                    if (window.loadEmotions) {
                        window.loadEmotions().catch(err => console.error('Emotions load error', err));
                    }
                } else if (nextTab === 'designer') {
                    loadDesignedVoices();
                } else if (nextTab === 'training') {
                    loadLoraDatasets();
                    loadLoraModels();
                } else if (nextTab === 'dataset-builder') {
                    dsbLoadProjects(dsbCurrentProject);
                } else if (nextTab === 'audio') {
                    if (window.populateExportChapterSelect) window.populateExportChapterSelect();
                } else if (nextTab === 'proofread') {
                    if (window.loadProofreadData) {
                        window.loadProofreadData({ includeChapters: true }).catch(err => console.error('Proofread load error', err));
                    }
                }

                if (typeof reconnectTaskLogs === 'function') {
                    reconnectTaskLogs().catch(err => console.error('Task log reconnect error', err));
                }
            });
        });
