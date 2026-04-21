import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SETUP_TAB_JS = ROOT / "app" / "static" / "js" / "legacy" / "03_setup_tab.js"


class SetupTabLMStudioModelPickerTests(unittest.TestCase):
    maxDiff = None

    def _run_node_test(self, body: str):
        script = textwrap.dedent(
            f"""
            const assert = require('assert');
            const fs = require('fs');
            const vm = require('vm');

            const source = fs.readFileSync({str(SETUP_TAB_JS)!r}, 'utf8')
                + '\\nthis.__setupTabTestHooks = {{ _fetchLMStudioModelSuggestions, _isKnownLMStudioModelSuggestion }};';

            function createClassList(initial = []) {{
                const values = new Set(initial);
                return {{
                    add(name) {{ values.add(name); }},
                    remove(name) {{ values.delete(name); }},
                    contains(name) {{ return values.has(name); }},
                    toggle(name, force) {{
                        if (force === undefined) {{
                            if (values.has(name)) {{ values.delete(name); return false; }}
                            values.add(name);
                            return true;
                        }}
                        if (force) {{ values.add(name); return true; }}
                        values.delete(name);
                        return false;
                    }},
                }};
            }}

            function createElement(tagName = 'DIV', initialValue = '') {{
                const listeners = {{}};
                let inner = '';
                const children = [];
                const element = {{
                    tagName,
                    type: 'text',
                    value: initialValue,
                    checked: false,
                    dataset: {{}},
                    style: {{}},
                    className: '',
                    classList: createClassList(),
                    title: '',
                    options: [],
                    addEventListener(type, handler) {{
                        listeners[type] = listeners[type] || [];
                        listeners[type].push(handler);
                    }},
                    emit(type, payload = undefined) {{
                        const event = payload || {{ type, target: element, preventDefault() {{}} }};
                        if (!event.target) event.target = element;
                        for (const handler of listeners[type] || []) {{
                            handler(event);
                        }}
                    }},
                    dispatchEvent(event) {{
                        const evt = event || {{ type: '' }};
                        this.emit(String(evt.type || ''), evt);
                        return true;
                    }},
                    appendChild(child) {{
                        children.push(child);
                        this.options = children;
                        return child;
                    }},
                    contains(target) {{
                        return children.includes(target);
                    }},
                    setAttribute(name, value) {{
                        this[name] = value;
                    }},
                    getAttribute(name) {{
                        return this[name];
                    }},
                }};
                Object.defineProperty(element, 'innerHTML', {{
                    get() {{ return inner; }},
                    set(value) {{
                        inner = String(value || '');
                        if (inner === '') {{
                            children.length = 0;
                            element.options = children;
                        }}
                    }},
                }});
                Object.defineProperty(element, 'childElementCount', {{
                    get() {{ return children.length; }},
                }});
                return element;
            }}

            function createContext(apiPost) {{
                const llmModel = createElement('INPUT', '');
                const llmUrl = createElement('INPUT', 'http://127.0.0.1:1234/v1');
                const llmKey = createElement('INPUT', 'local');
                const legacyMode = createElement('INPUT', '');
                legacyMode.type = 'checkbox';
                legacyMode.checked = false;
                const capabilityStatus = createElement('SPAN', '');
                const modelSuggestionsPopup = createElement('DIV', '');
                const configForm = createElement('FORM', '');

                const elements = {{
                    'llm-model': llmModel,
                    'llm-url': llmUrl,
                    'llm-key': llmKey,
                    'legacy-mode-toggle': legacyMode,
                    'llm-tool-capability-status': capabilityStatus,
                    'llm-model-suggestion-popup': modelSuggestionsPopup,
                    'config-form': configForm,
                }};

                const toasts = [];
                const apiCalls = [];

                const context = {{
                    console,
                    Promise,
                    setTimeout: (fn, ms) => global.setTimeout(fn, ms),
                    clearTimeout: (id) => global.clearTimeout(id),
                    Event: function Event(type, init = {{}}) {{
                        this.type = type;
                        this.bubbles = !!init.bubbles;
                        this.cancelable = !!init.cancelable;
                        this.defaultPrevented = false;
                        this.preventDefault = () => {{ this.defaultPrevented = true; }};
                    }},
                    API: {{
                        post: async (url, payload) => {{
                            apiCalls.push({{ url, payload }});
                            return apiPost(url, payload);
                        }},
                        get: async () => ({{}}),
                    }},
                    showToast: (message, level) => toasts.push({{ message, level }}),
                    showConfirm: async () => true,
                    navigator: {{
                        userAgentData: {{ platform: 'MacIntel' }},
                        platform: 'MacIntel',
                        userAgent: 'Mozilla/5.0',
                        sendBeacon: () => true,
                    }},
                    window: null,
                    document: {{
                        body: {{ dataset: {{}} }},
                        getElementById: (id) => elements[id] || null,
                        querySelectorAll: () => [],
                        createElement: (tag) => createElement(String(tag || 'div').toUpperCase(), ''),
                        addEventListener: () => {{}},
                    }},
                    refreshPromptTextareaHeights: () => {{}},
                    applyTheme: () => {{}},
                    applyGenerationModeLock: () => {{}},
                    localStorage: {{ getItem: () => null, setItem: () => {{}} }},
                }};
                context.window = context;
                context.window.location = {{ reload() {{}} }};
                context.window.addEventListener = () => {{}};

                context.__elements = elements;
                context.__toasts = toasts;
                context.__apiCalls = apiCalls;
                return context;
            }}

            async function tick(ms = 0) {{
                await new Promise((resolve) => setTimeout(resolve, ms));
            }}

            {body}
            """
        )

        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
            handle.write(script)
            path = handle.name

        try:
            completed = subprocess.run(["node", path], capture_output=True, text=True, check=False)
        finally:
            Path(path).unlink(missing_ok=True)

        if completed.returncode != 0:
            raise AssertionError(
                "Node test failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

    def test_focus_populates_model_suggestions(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext(async (url) => {
                    if (url === '/api/config/lmstudio/list_models') {
                        return {
                            status: 'ok',
                            models: [
                                { key: 'qwen/qwen3.5-9b', display_name: 'Qwen3.5 9B' },
                                { key: 'google/gemma-4-27b', display_name: 'Gemma 4 27B' },
                            ],
                        };
                    }
                    if (url === '/api/config/verify_tool_capability') {
                        return { status: 'supported', message: 'ok' };
                    }
                    throw new Error(`Unexpected API call: ${url}`);
                });

                vm.createContext(context);
                vm.runInContext(source, context);

                context.__elements['llm-model'].emit('focus');
                await tick();

                const popup = context.__elements['llm-model-suggestion-popup'];
                const options = popup.options;
                assert.strictEqual(options.length, 2);
                assert.strictEqual(popup.style.display, '');
                assert.strictEqual(options[0].dataset.modelKey, 'qwen/qwen3.5-9b');
                assert.strictEqual(options[1].dataset.modelKey, 'google/gemma-4-27b');
                assert.strictEqual(
                    context.__apiCalls.filter(call => call.url === '/api/config/lmstudio/list_models').length,
                    1
                );
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_unreachable_lmstudio_silently_hides_suggestions(self):
        self._run_node_test(
            """
            (async () => {
                const context = createContext(async (url) => {
                    if (url === '/api/config/lmstudio/list_models') {
                        throw new Error('offline');
                    }
                    if (url === '/api/config/verify_tool_capability') {
                        return { status: 'supported', message: 'ok' };
                    }
                    throw new Error(`Unexpected API call: ${url}`);
                });

                vm.createContext(context);
                vm.runInContext(source, context);

                context.__elements['llm-model'].emit('focus');
                await tick();

                const popup = context.__elements['llm-model-suggestion-popup'];
                assert.strictEqual(popup.options.length, 0);
                assert.strictEqual(popup.style.display, 'none');
                assert.strictEqual(context.__toasts.length, 0, 'failure should remain silent in UI');
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_selecting_suggested_model_triggers_immediate_capability_verification(self):
        self._run_node_test(
            """
            (async () => {
                let verifyCalls = 0;
                const context = createContext(async (url, payload) => {
                    if (url === '/api/config/lmstudio/list_models') {
                        return {
                            status: 'ok',
                            models: [
                                { key: 'qwen/qwen3.5-9b', display_name: 'Qwen3.5 9B' },
                            ],
                        };
                    }
                    if (url === '/api/config/verify_tool_capability') {
                        verifyCalls += 1;
                        assert.strictEqual(payload.model_name, 'qwen/qwen3.5-9b');
                        return { status: 'supported', message: 'ok' };
                    }
                    throw new Error(`Unexpected API call: ${url}`);
                });

                vm.createContext(context);
                vm.runInContext(source, context);

                context.__elements['llm-model'].emit('focus');
                await tick();

                const popup = context.__elements['llm-model-suggestion-popup'];
                assert.strictEqual(popup.options.length, 1);
                popup.options[0].emit('click');
                await tick();

                assert.ok(verifyCalls >= 1, 'known suggestion should verify immediately');
                assert.strictEqual(context.__elements['llm-model'].value, 'qwen/qwen3.5-9b');
                assert.strictEqual(popup.style.display, 'none');
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )

    def test_suggestion_cache_invalidates_when_llm_url_changes(self):
        self._run_node_test(
            """
            (async () => {
                let listCalls = 0;
                const context = createContext(async (url) => {
                    if (url === '/api/config/lmstudio/list_models') {
                        listCalls += 1;
                        return { status: 'ok', models: [{ key: 'qwen/qwen3.5-9b', display_name: 'Qwen3.5 9B' }] };
                    }
                    if (url === '/api/config/verify_tool_capability') {
                        return { status: 'supported', message: 'ok' };
                    }
                    throw new Error(`Unexpected API call: ${url}`);
                });

                vm.createContext(context);
                vm.runInContext(source, context);

                context.__elements['llm-model'].emit('focus');
                await tick();
                context.__elements['llm-model'].emit('focus');
                await tick();
                assert.strictEqual(listCalls, 1, 'second focus should use cache');

                context.__elements['llm-url'].value = 'http://127.0.0.1:2234/v1';
                context.__elements['llm-url'].emit('input');
                context.__elements['llm-model'].emit('focus');
                await tick();
                assert.strictEqual(listCalls, 2, 'url change should invalidate cache');
            })().catch((error) => {
                console.error(error);
                process.exit(1);
            });
            """
        )


if __name__ == "__main__":
    unittest.main()
