-- Local-only, typed mailbox bridge. Loaded after PoB's normal frame callback.
-- No arbitrary Lua evaluation, network listener, or changes to calculation rules.
local main, options = ...
options = options or {}
local json = require("dkjson")
local root = GetScriptPath():gsub("\\", "/"):gsub("/$", "")
local base = root .. "/agent-bridge/runtime/"
local ffi = require("ffi")
ffi.cdef[[
unsigned long GetCurrentProcessId(void);
void *CreateMutexA(void *, int, const char *);
unsigned long GetLastError(void);
int CloseHandle(void *);
]]
local pid = tonumber(ffi.C.GetCurrentProcessId())
local handle = ffi.C.CreateMutexA(nil, 0, "Local\\PoBAgentBridge_" .. root:gsub("[^%w]", "_"))
if handle == nil or ffi.C.GetLastError() == 183 then
    if handle ~= nil then ffi.C.CloseHandle(handle) end
    return { tick = function() end }
end
handle = ffi.gc(handle, ffi.C.CloseHandle)
local bridge = { mutex = handle, last = nil, heartbeatAt = -math.huge, closed = false }
local stats = {"Life","LifeUnreserved","ManaUnreserved","ManaCost","LifeCost","Str","Dex","Int","ReqStr","ReqDex","ReqInt","CombinedDPS","FullDPS","HitChance","PoisonChance","Speed","CritChance","PoisonDuration","ChainMax","FrenzyCharges","EnduranceCharges","AfflictionCharges","FireResist","ColdResist","LightningResist","ChaosResist","BlockChance","SpellBlockChance","SpellSuppressionChance","EvadeChance","PhysicalMaximumHitTaken","FireMaximumHitTaken","ColdMaximumHitTaken","LightningMaximumHitTaken","ChaosMaximumHitTaken","LifeRegenRecovery","LifeLeechGainRate","ManaRegenRecovery","ManaLeechGainRate","MovementSpeedMod"}
local views={TREE=true,SKILLS=true,ITEMS=true,CALCS=true,CONFIG=true,NOTES=true,IMPORT=true}
local function read(path)
    local f=io.open(path,"rb");if not f then return nil end
    local text=f:read("*a");f:close();return text
end
local function write(path,text)
    local f=assert(io.open(path,"wb"));f:write(text);f:close()
end
local function pathWithin(path)
    assert(type(path)=="string" and not path:find("%z"),"path must be a string")
    path=path:gsub("\\","/")
    assert(not path:match("[<>|?*]") and not path:find("..",1,true),"unsafe path")
    if not path:match("^%a:/") then path=root.."/"..path end
    assert(path:sub(1,#root+1):lower()==(root.."/"):lower(),"path must be inside the PoB workspace")
    assert(not path:sub(3):find(":",1,true),"alternate streams are not allowed")
    assert(path:lower():match("%.xml$"),"expected an XML build file")
    return path
end
local function build()
    assert(main.mode=="BUILD" and main.modes.BUILD.calcsTab,"no active calculated build")
    return main.modes.BUILD
end
-- These are the non-drawing lifecycle steps from PoB 2.67.2 Main/Build.
-- Do not call OnFrame from a timer: it processes input and renders the UI.
local function settle()
    local transitions = 0
    while main.newMode do
        transitions = transitions + 1
        assert(transitions <= 4, 'PoB could not finish its mode transition')
        if main.mode then main:CallMode('Shutdown') end
        main.mode = main.newMode
        main.newMode = nil
        main:CallMode('Init', unpack(main.newModeArgs))
        if main.newModeChangeToTree then main.modes[main.mode].viewMode = 'TREE' end
        main.newModeChangeToTree = false
    end
    if main.mode ~= 'BUILD' or not main.modes.BUILD.calcsTab then return end
    local b = build()
    if b.buildFlag then
        wipeGlobalCache()
        b.outputRevision = b.outputRevision + 1
        b.buildFlag = false
        b.skillsTab:UpdateSocketGroups()
        b.calcsTab:BuildOutput()
        b:RefreshStatList()
        b.configTab.calcFunc, b.configTab.calcBase = b.calcsTab:GetMiscCalculator(b)
    end
    b.unsaved = not not (b.modFlag or b.notesTab.modFlag or b.partyTab.modFlag or
        b.configTab.modFlag or b.treeTab.modFlag or b.treeTab.searchFlag or
        b.spec.modFlag or b.skillsTab.modFlag or b.itemsTab.modFlag or b.calcsTab.modFlag)
end
local function snapshot()
    local r={bridgeVersion="0.2.0",pid=pid,pobVersion=launch.versionNumber,latestTreeVersion=latestTreeVersion,mode=main.mode,modalCount=#main.popups,serviceMode=bridge.timer and 'windows-message-timer' or 'manual-frame',runtimeError=not not launch.promptMsg}
    if main.mode~="BUILD" or not main.modes.BUILD.calcsTab then return r end
    local b=build()
    r.name=b.buildName;r.file=b.dbFileName;r.unsaved=not not b.unsaved;r.view=b.viewMode
    r.level=b.characterLevel;r.tree=b.treeTab.activeSpec;r.skills=b.skillsTab.activeSkillSetId;r.items=b.itemsTab.activeItemSetId
    r.configSet=b.configTab.activeConfigSetId;r.mainSkillGroup=b.mainSocketGroup;r.points={b.spec:CountAllocNodes()};r.stats={};r.trees={};r.skillSets={};r.itemSets={};r.configSets={};r.gems={}
    for _,k in ipairs(stats) do r.stats[k]=b.calcsTab.mainOutput[k] end
    for i,s in ipairs(b.treeTab.specList) do table.insert(r.trees,{id=i,title=s.title or "Default",version=s.treeVersion}) end
    for _,i in ipairs(b.skillsTab.skillSetOrderList) do local s=b.skillsTab.skillSets[i];table.insert(r.skillSets,{id=i,title=s.title or "Default"}) end
    for _,i in ipairs(b.itemsTab.itemSetOrderList) do local s=b.itemsTab.itemSets[i];table.insert(r.itemSets,{id=i,title=s.title or "Default"}) end
    for _,i in ipairs(b.configTab.configSetOrderList) do local s=b.configTab.configSets[i];table.insert(r.configSets,{id=i,title=s.title or "Default"}) end
    for i,g in ipairs(b.skillsTab.socketGroupList) do
        local group={id=i,label=g.label,slot=g.slot,enabled=g.enabled,gems={}}
        for _,gem in ipairs(g.gemList) do table.insert(group.gems,{name=gem.nameSpec,level=gem.level,quality=gem.quality,enabled=gem.enabled}) end
        table.insert(r.gems,group)
    end
    return r
end
local function preserve(id)
    if main.mode=="BUILD" and main.modes.BUILD.calcsTab then
        local b=build();local p=base.."before-"..id..".xml"
        assert(not read(p),"backup already exists")
        write(p,assert(b:SaveDB(b.buildName)))
        return p
    end
end
local function index(value,list,label)
    assert(type(value)=="number" and value%1==0 and list[value],"unknown "..label.." id")
    return value
end
local handlers={}
handlers.status=function() return {result=snapshot()} end
handlers.load=function(a,id)
    assert(not launch.promptMsg,'Resolve the active PoB runtime error before loading')
    assert(#main.popups==0,"close the active PoB dialog before loading")
    local path=pathWithin(a.path);local xml=assert(read(path),"build file not found")
    assert(#xml<16*1024*1024 and xml:find("<PathOfBuilding",1,true),"invalid/oversized build XML")
    local parsed,err=require("xml").ParseXML(xml)
    assert(parsed and parsed[1] and parsed[1].elem=="PathOfBuilding",err or "invalid build XML")
    local backup=preserve(id)
    local name=a.name or path:match("([^/]+)%.xml$")
    assert(type(name)=="string" and #name<200,"invalid build name")
    main:SetMode("BUILD",false,name,xml)
    settle()
    local result=snapshot();result.backup=backup;result.loaded=path
    return {result=result}
end
handlers.select=function(a)
    local b=build();assert(#main.popups==0,"close the active PoB dialog first")
    -- Validate every supplied field before mutating any part of the loadout.
    if a.tree then index(a.tree,b.treeTab.specList,"tree") end
    if a.skills then index(a.skills,b.skillsTab.skillSets,"skill set") end
    if a.items then index(a.items,b.itemsTab.itemSets,"item set") end
    if a.configSet then index(a.configSet,b.configTab.configSets,"config set") end
    if a.view then assert(views[a.view],"invalid view") end
    local groups=a.skills and b.skillsTab.skillSets[a.skills].socketGroupList or b.skillsTab.socketGroupList
    if a.mainSkillGroup then index(a.mainSkillGroup,groups,"main skill group") end
    if a.tree then b.treeTab:SetActiveSpec(a.tree) end
    if a.skills then b.skillsTab:SetActiveSkillSet(a.skills) end
    if a.items then b.itemsTab:SetActiveItemSet(a.items) end
    if a.configSet then b.configTab:SetActiveConfigSet(a.configSet) end
    if a.view then b.viewMode=a.view end
    if a.mainSkillGroup then b.mainSocketGroup=a.mainSkillGroup end
    b.modFlag=true;b.buildFlag=true
    settle()
    return {result=snapshot()}
end
handlers.config=function(a)
    local b=build();assert(#main.popups==0,"close the active PoB dialog first");assert(type(a.values)=="table","values object required")
    for k,v in pairs(a.values) do
        assert(type(k)=="string" and #k<150,"invalid config name")
        assert(type(v)=="boolean" or type(v)=="number" or (type(v)=="string" and #v<500),"config values must be scalar")
    end
    for k,v in pairs(a.values) do b.configTab.input[k]=v end
    b.configTab:UpdateControls()
    b.configTab:BuildModList();b.modFlag=true;b.buildFlag=true
    settle()
    return {result=snapshot()}
end
handlers.export=function(a)
    local b=build();local path=pathWithin(a.path)
    assert(not read(path),"export destination already exists; choose a new filename")
    write(path,assert(b:SaveDB(b.buildName)))
    return {result={path=path,snapshot=snapshot()}}
end
function bridge:respond(id,ok,result)
    write(base.."response.json",assert(json.encode({id=id,ok=ok,result=ok and result or nil,error=not ok and tostring(result) or nil})))
end
function bridge:process()
    local now=GetTime()
    if now-self.heartbeatAt>=1000 then
        self.heartbeatAt=now
        write(base.."heartbeat.json",assert(json.encode({pid=pid,version="0.2.0",time=os.time(),serviceMode=self.timer and 'windows-message-timer' or 'manual-frame',lastError=self.lastError})))
    end
    local text=read(base.."request.json");if not text then return end
    local req=json.decode(text)
    if not req or req.id==self.last or req.pid~=pid then return end
    if type(req.id)~="string" or not req.id:match("^[a-f0-9]+$") or #req.id~=32 then return end
    self.last=req.id
    local ok,r=pcall(function()
        assert(not launch.promptMsg,'Resolve the active PoB runtime error first')
        assert(handlers[req.command],"unknown bridge command")
        settle()
        return handlers[req.command](req.args or {},req.id)
    end)
    if not ok then self:respond(req.id,false,r)
    else self:respond(req.id,true,r.result) end
end
function bridge:pump()
    if self.closed or self.busy or (self.callbackDepth or 0)>0 then return end
    self.busy=true
    local cwd
    local ok,err=pcall(function()
        cwd=GetWorkDir and GetWorkDir()
        if SetWorkDir then SetWorkDir(root) end
        self:process()
    end)
    if cwd and SetWorkDir then pcall(SetWorkDir,cwd) end
    self.busy=false
    if not ok then error(err) end
end
function bridge:tick()
    -- The old startup hook remains compatible; timer mode does not poll per frame.
    if not self.timer then return self:pump() end
end
function bridge:recordError(err)
    self.lastError=tostring(err)
    pcall(write,base..'last-error.json',assert(json.encode({time=os.time(),error=self.lastError})))
end
function bridge:close()
    self.closed=true
    if self.timer then self.timer:close() end
    for name,entry in pairs(self.wrapped or {}) do
        if launch[name]==entry.wrapper then launch[name]=entry.original end
    end
    if self.mutex then ffi.gc(self.mutex,nil);ffi.C.CloseHandle(self.mutex);self.mutex=nil end
end
if options.timer ~= false then
    local start=assert(loadfile(root..'/agent-bridge/timer.lua'))()
    bridge.timer=start(function() bridge:pump() end,function(err) bridge:recordError(err) end)
    -- Native modal dialogs can dispatch timer messages from inside a Lua UI
    -- callback. Wait for that callback to unwind rather than re-enter its build.
    bridge.wrapped={}
    local function packed(...) return {n=select('#',...),...} end
    for _,name in ipairs({'OnFrame','OnKeyDown','OnKeyUp','OnChar','OnSubCall','OnSubError','OnSubFinished'}) do
        local original=launch[name]
        if original then
            local function wrapper(...)
                bridge.callbackDepth=(bridge.callbackDepth or 0)+1
                local result=packed(pcall(original,...))
                bridge.callbackDepth=bridge.callbackDepth-1
                if not result[1] then error(result[2],0) end
                return unpack(result,2,result.n)
            end
            bridge.wrapped[name]={original=original,wrapper=wrapper}
            launch[name]=wrapper
        end
    end
    -- Keep native callback storage alive until OnExit kills and drains its timer.
    local originalExit=launch.OnExit
    local exitWrapper=function(self,...)
        bridge:close()
        if originalExit then return originalExit(self,...) end
    end
    bridge.wrapped.OnExit={original=originalExit,wrapper=exitWrapper}
    launch.OnExit=exitWrapper
end
return bridge
