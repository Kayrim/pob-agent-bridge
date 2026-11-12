-- Same-thread, message-only Windows timer. No foreground, input or drawing API.
-- DispatchMessage invokes TIMERPROC on PoB's UI thread even when rendering idles.
local ffi = require('ffi')
if not pcall(ffi.typeof, 'PoBAgentTimerMessage') then
    ffi.cdef[[
    typedef struct {
        void *hwnd; unsigned int message; uintptr_t wParam; intptr_t lParam;
        unsigned long time; long pointX; long pointY; unsigned long privateValue;
    } PoBAgentTimerMessage;
    typedef void (__stdcall *PoBAgentTimerProc)(void *, unsigned int, uintptr_t, unsigned long);
    void * __stdcall CreateWindowExA(unsigned long, const char *, const char *, unsigned long,
        int, int, int, int, void *, void *, void *, void *);
    uintptr_t __stdcall SetTimer(void *, uintptr_t, unsigned int, PoBAgentTimerProc);
    int __stdcall KillTimer(void *, uintptr_t);
    int __stdcall DestroyWindow(void *);
    int __stdcall PeekMessageA(PoBAgentTimerMessage *, void *, unsigned int, unsigned int, unsigned int);
    intptr_t __stdcall DispatchMessageA(const PoBAgentTimerMessage *);
    unsigned long GetCurrentThreadId(void);
    ]]
end

return function(callback, onError)
    local api = ffi.load('user32')
    local timer = { api = api, threadId = tonumber(ffi.C.GetCurrentThreadId()), active = false }
    -- A private message-only STATIC window gives cleanup an exact message filter.
    -- No visible window is created, and no callback is installed on PoB's window.
    timer.window = api.CreateWindowExA(0, 'STATIC', 'PoB Agent Bridge', 0, 0, 0, 0, 0,
        ffi.cast('void *', -3), nil, nil, nil)
    assert(timer.window ~= nil, 'Could not create the bridge message window')
    local function dispatch()
        if not timer.active then return end
        local ok, err = pcall(callback)
        if not ok and onError then pcall(onError, tostring(err)) end
    end
    -- A callback may not unwind through the native message pump or be JIT-inlined.
    jit.off(dispatch, true)
    timer.callback = ffi.cast('PoBAgentTimerProc', dispatch)
    if api.SetTimer(timer.window, 1, 100, timer.callback) == 0 then
        api.DestroyWindow(timer.window)
        timer.callback:free()
        error('Could not start the bridge message timer')
    end
    timer.active = true
    function timer:close()
        if not self.active then return end
        self.active = false
        api.KillTimer(self.window, 1)
        -- KillTimer does not remove already posted WM_TIMER messages. Drain only
        -- our private window before freeing the Lua callback (also on restart).
        local message = ffi.new('PoBAgentTimerMessage[1]')
        while api.PeekMessageA(message, self.window, 0x113, 0x113, 1) ~= 0 do end
        api.DestroyWindow(self.window)
        self.callback:free()
    end
    return timer
end
