"""Editor tab legacy JS harness tests split by behavior area."""

from ._editor_tab_node_harness import EditorTabChunkPollTests


class EditorNarratorAndChaptersTests(EditorTabChunkPollTests):
    def test_narrator_selection_is_saved_before_reload_and_not_reverted(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 1');
                context.localStorage.setItem('threadspeak-narrator-selection', JSON.stringify({ 'Chapter 1': 'Old Voice' }));

                const select = context.document.getElementById('editor-narrator-select');
                select.value = 'New Voice';

                context.__editorTabTestHooks.setCachedChunks([
                    { id: 1, speaker: 'NARRATOR', text: 'Narrator line', chapter: 'Chapter 1', audio_path: 'voicelines/existing.mp3' }
                ]);

                let selectionSeenDuringReload = null;
                context.__editorTabTestHooks.setLoadChunks(async () => {
                    selectionSeenDuringReload = context.__editorTabTestHooks.getNarratorSelections()['Chapter 1'] || null;
                });

                context.API.post = async (url, payload) => {
                    assert.strictEqual(url, '/api/narrator_overrides');
                    assert.strictEqual(payload.chapter, 'Chapter 1');
                    assert.strictEqual(payload.voice, 'New Voice');
                    assert.strictEqual(payload.invalidate_audio, true);
                    return { status: 'saved' };
                };

                await context.window.onNarratorSelectorChange();

                const finalSelections = context.__editorTabTestHooks.getNarratorSelections();
                assert.strictEqual(selectionSeenDuringReload, 'New Voice', 'loadChunks should observe the new selection, not the stale one');
                assert.strictEqual(finalSelections['Chapter 1'], 'New Voice');
            })().catch((error) => {{
                console.error(error);
                process.exit(1);
            }});
            """
        )

    def test_update_narrator_selector_uses_backend_candidate_order(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 6');
                context.__editorTabTestHooks.setCachedChunks([
                    { id: 1, speaker: 'NARRATOR', text: 'Ryan looks over. Blake answers. Blake waits beside Ryan while Blake nods.', chapter: 'Chapter 6', audio_path: null },
                ]);

                context.API.get = async (url) => {
                    if (url === '/api/voices') {
                        return [
                            { name: 'NARRATOR', config: { narrates: true } },
                            { name: 'Ryan', config: { narrates: true } },
                            { name: 'Blake', config: { narrates: true } },
                        ];
                    }
                    if (url === '/api/narrator_candidates?chapter=Chapter%206') {
                        return { chapter: 'Chapter 6', voices: ['NARRATOR', 'Blake', 'Ryan'] };
                    }
                    throw new Error(`Unexpected GET ${url}`);
                };

                await context.updateNarratorSelector(context.__editorTabTestHooks.getCachedChunks());

                const select = context.document.getElementById('editor-narrator-select');
                assert.ok(select.innerHTML.indexOf('value="Blake"') < select.innerHTML.indexOf('value="Ryan"'));
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_update_narrator_selector_does_not_reinsert_disabled_narrator(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 6');
                context.__editorTabTestHooks.setCachedChunks([
                    { id: 1, speaker: 'NARRATOR', text: 'Ryan looks over. Blake answers. Blake waits beside Ryan while Blake nods.', chapter: 'Chapter 6', audio_path: null },
                ]);

                context.API.get = async (url) => {
                    if (url === '/api/voices') {
                        return [
                            { name: 'NARRATOR', config: { narrates: false } },
                            { name: 'Ryan', config: { narrates: true } },
                            { name: 'Blake', config: { narrates: true } },
                        ];
                    }
                    if (url === '/api/narrator_candidates?chapter=Chapter%206') {
                        return { chapter: 'Chapter 6', voices: ['Blake', 'Ryan'] };
                    }
                    throw new Error(`Unexpected GET ${url}`);
                };

                await context.updateNarratorSelector(context.__editorTabTestHooks.getCachedChunks());

                const select = context.document.getElementById('editor-narrator-select');
                assert.ok(!select.innerHTML.includes('value="NARRATOR"'));
                assert.ok(select.innerHTML.includes('value="Blake" selected'));
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_update_narrator_selector_local_fallback_excludes_disabled_narrator(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 6');
                context.__editorTabTestHooks.setCachedChunks([
                    { id: 1, speaker: 'NARRATOR', text: 'Ryan looks over. Blake answers. Blake waits beside Ryan while Blake nods.', chapter: 'Chapter 6', audio_path: null },
                ]);

                context.API.get = async (url) => {
                    if (url === '/api/voices') {
                        return [
                            { name: 'NARRATOR', config: { narrates: false } },
                            { name: 'Ryan', config: { narrates: true } },
                            { name: 'Blake', config: { narrates: true } },
                        ];
                    }
                    if (url === '/api/narrator_candidates?chapter=Chapter%206') {
                        throw new Error('backend unavailable');
                    }
                    throw new Error(`Unexpected GET ${url}`);
                };

                await context.updateNarratorSelector(context.__editorTabTestHooks.getCachedChunks());

                const select = context.document.getElementById('editor-narrator-select');
                assert.ok(!select.innerHTML.includes('value="NARRATOR"'));
                assert.ok(select.innerHTML.includes('value="Blake" selected'));
                assert.ok(select.innerHTML.indexOf('value="Blake"') < select.innerHTML.indexOf('value="Ryan"'));
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_editor_chapter_options_show_non_default_narrator_label(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 1');
                context.API.get = async (url) => {
                    if (url === '/api/chunks/chapters') {
                        return {
                            chapters: [
                                { chapter: 'Chapter 1', chunk_count: 1, narrator_label: 'Alice' },
                                { chapter: 'Chapter 2', chunk_count: 1, narrator_label: '' },
                            ],
                        };
                    }
                    if (url === '/api/chunks/view?chapter=Chapter%201') {
                        return [
                            { id: 1, uid: 'chunk-1', speaker: 'Narrator', chapter: 'Chapter 1', text: 'one', instruct: '', status: 'done', audio_path: null, audio_validation: null },
                        ];
                    }
                    if (url === '/api/voices') {
                        return [];
                    }
                    if (url === '/api/narrator_candidates?chapter=Chapter%201') {
                        return { chapter: 'Chapter 1', voices: ['NARRATOR'] };
                    }
                    throw new Error(`Unexpected GET ${url}`);
                };

                await context.loadChunks(true);
                await flushTicks();

                const select = context.document.getElementById('editor-chapter-select');
                assert.ok(select.innerHTML.includes('Chapter 1 N: Alice (1)'));
                assert.ok(select.innerHTML.includes('Chapter 2 (1)'));
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_editor_chapter_options_rerender_when_only_narrator_label_changes(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                const chapters = [
                    { chapter: 'Chapter 1', chunk_count: 1, narrator_label: '' },
                ];

                context.__editorTabTestHooks.setSelectedEditorChapter('Chapter 1');
                context.API.get = async (url) => {
                    if (url === '/api/chunks/chapters') {
                        return { chapters };
                    }
                    if (url === '/api/chunks/view?chapter=Chapter%201') {
                        return [
                            { id: 1, uid: 'chunk-1', speaker: 'Narrator', chapter: 'Chapter 1', text: 'one', instruct: '', status: 'done', audio_path: null, audio_validation: null },
                        ];
                    }
                    if (url === '/api/voices') {
                        return [];
                    }
                    if (url === '/api/narrator_candidates?chapter=Chapter%201') {
                        return { chapter: 'Chapter 1', voices: ['NARRATOR'] };
                    }
                    throw new Error(`Unexpected GET ${url}`);
                };

                await context.loadChunks(true);
                await flushTicks();

                const select = context.document.getElementById('editor-chapter-select');
                assert.ok(select.innerHTML.includes('Chapter 1 (1)'));

                chapters[0].narrator_label = 'Alice';
                context.syncEditorChapterState(context.__editorTabTestHooks.getCachedChunks());
                await flushTicks();

                assert.ok(select.innerHTML.includes('Chapter 1 N: Alice (1)'));
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_sync_narrator_selections_from_backend_replaces_stale_local_entries(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext();
                vm.createContext(context);
                vm.runInContext(source, context);

                context.localStorage.setItem('threadspeak-narrator-selection', JSON.stringify({
                    'Chapter 1': 'Old Voice',
                    'Chapter 2': 'Another Voice',
                }));

                context.API.get = async (url) => {
                    assert.strictEqual(url, '/api/narrator_overrides');
                    return { 'Chapter 1': 'Fresh Voice' };
                };

                await context.syncNarratorSelectionsFromBackend();

                const finalSelections = context.__editorTabTestHooks.getNarratorSelections();
                assert.strictEqual(JSON.stringify(finalSelections), JSON.stringify({ 'Chapter 1': 'Fresh Voice' }));
            })().catch((error) => {{
                console.error(error);
                process.exit(1);
            }});
            """
        )

if __name__ == "__main__":
    unittest.main()

