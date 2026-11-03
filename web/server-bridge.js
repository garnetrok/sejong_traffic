/**
 * Apps Script의 google.script.run 호출을 Flask API(/api/<함수명>) 호출로 바꿔 주는 브리지.
 * script.html 은 원래 Apps Script용으로 작성되어 있어서, 이 파일만 있으면 수정 없이 그대로 동작함.
 *
 *   google.script.run.withSuccessHandler(fn).fetchTrafficData("mock_accident_data")
 *   → POST /api/fetchTrafficData  { "args": ["mock_accident_data"] }  → fn(result)
 */
(function () {
    function makeRunner() {
        let onSuccess = null;
        let onFailure = null;
        const runner = new Proxy({}, {
            get(_, name) {
                if (name === 'withSuccessHandler') return fn => { onSuccess = fn; return runner; };
                if (name === 'withFailureHandler') return fn => { onFailure = fn; return runner; };
                if (name === 'withUserObject') return () => runner;
                return (...args) => {
                    fetch('/api/' + encodeURIComponent(name), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ args })
                    })
                        .then(r => r.json().catch(() => ({})).then(body => {
                            if (!r.ok) throw new Error(body.error || ('HTTP ' + r.status));
                            return body.result;
                        }))
                        .then(result => { if (onSuccess) onSuccess(result); })
                        .catch(err => {
                            console.error('[server-bridge] ' + name + ' 실패:', err);
                            if (onFailure) onFailure(err);
                            else alert('서버 호출 실패 (' + name + '): ' + err.message);
                        });
                };
            }
        });
        return runner;
    }

    window.google = window.google || {};
    window.google.script = window.google.script || {};
    Object.defineProperty(window.google.script, 'run', { get: makeRunner });
})();
