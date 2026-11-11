"""Run the installed PoB engine through its matching upstream headless wrapper.

Only bridge runtime files can be written. User settings/updater are disabled.
Calculations use the locally installed PoB engine and game data.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import sys


ROOT = Path(sys.argv[1]).resolve()
RESEARCH = ROOT / "agent-bridge" / "runtime"
RESEARCH.mkdir(parents=True, exist_ok=True)


def run(lua_script: str) -> None:
    os.chdir(ROOT)
    dll_directory = os.add_dll_directory(str(ROOT))
    dll = ctypes.CDLL(str(ROOT / "lua51.dll"))
    dll.luaL_newstate.restype = ctypes.c_void_p
    dll.luaL_openlibs.argtypes = [ctypes.c_void_p]
    dll.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    dll.luaL_loadstring.restype = ctypes.c_int
    dll.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    dll.lua_pcall.restype = ctypes.c_int
    dll.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    dll.lua_tolstring.restype = ctypes.c_char_p
    dll.lua_close.argtypes = [ctypes.c_void_p]
    state = dll.luaL_newstate()
    if not state:
        raise RuntimeError("Could not create Lua state")
    try:
        dll.luaL_openlibs(state)
        for chunk in [lua_script]:
            result = dll.luaL_loadstring(state, chunk.encode("utf-8"))
            if not result:
                result = dll.lua_pcall(state, 0, 0, 0)
            if result:
                message = dll.lua_tolstring(state, -1, None)
                raise RuntimeError(message.decode("utf-8", errors="replace") if message else str(result))
    finally:
        dll.lua_close(state)
        dll_directory.close()


def prelude() -> str:
    # The wrapper normally relies on host-provided SHA1 and engine paths.
    # Use the installed pure-Lua implementation with identical SHA1 semantics.
    # Exclude first.run so startup cannot trigger the install/update workflow.
    wrapper = (Path(__file__).parent / "vendor" / "HeadlessWrapper.lua").read_text(encoding="utf-8")
    wrapper = wrapper[wrapper.index("\n") + 1:]
    init = '''
GetScriptPath = function() return ROOT_PATH end
GetRuntimePath = function() return ROOT_PATH end
GetUserPath = function() return RESEARCH_PATH end
launch.CheckForUpdate = function() end
launch.agentBridgeTried = true
'''
    wrapper = wrapper.replace('dofile("Launch.lua")', 'dofile("Launch.lua")\n' + init)
    wrapper = wrapper.replace('io.read("*l")', 'error(mainObject.promptMsg)')
    return '''
ROOT_PATH = %s
RESEARCH_PATH = %s
package.path = "./lua/?.lua;./lua/?/init.lua;" .. package.path
package.cpath = "./?.dll;" .. package.cpath
arg = {}
package.preload.sha1 = function() return require("sha2").sha1 end
local originalOpen = io.open
io.open = function(path, mode)
    if path == "first.run" then return nil end
    if mode and (mode:find("w") or mode:find("a") or mode:find("+")) then
        local normalized = path:gsub("\\\\", "/")
        assert(not normalized:find("..", 1, true), "Parent path in write: " .. path)
        assert(normalized:sub(1, #RESEARCH_PATH + 1) == RESEARCH_PATH .. "/" or
               normalized:sub(1, 21) == "agent-bridge/runtime/", "Write outside research folder: " .. path)
    end
    return originalOpen(path, mode)
end
os.remove = function(path) error("Deletion disabled in research runner: " .. path) end
os.rename = function() error("Rename disabled in research runner") end
''' % (json.dumps(ROOT.as_posix()), json.dumps(RESEARCH.as_posix())) + wrapper


if __name__ == "__main__":
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("Native calculation needs Windows x64 and 64-bit Python")
    extra = (Path(__file__).parent / "calculate.lua").read_text(encoding="utf-8")
    run(prelude() + "\n" + extra)
