-- Local-only, typed mailbox bridge. Loaded after PoB's normal frame callback.
-- No arbitrary Lua evaluation, network listener, or changes to calculation rules.
local main = ...
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
local bridge = { mutex = handle, last = nil, pending = nil, heartbeatAt = -math.huge }
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
local function snapshot()
    local r={bridgeVersion="0.1.1",pid=pid,pobVersion=launch.versionNumber,latestTreeVersion=latestTreeVersion,mode=main.mode,modalCount=#main.popups}
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
    assert(#main.popups==0,"close the active PoB dialog before loading")
    local path=pathWithin(a.path);local xml=assert(read(path),"build file not found")
    assert(#xml<16*1024*1024 and xml:find("<PathOfBuilding",1,true),"invalid/oversized build XML")
    local parsed,err=require("xml").ParseXML(xml)
    assert(parsed and parsed[1] and parsed[1].elem=="PathOfBuilding",err or "invalid build XML")
    local backup=preserve(id)
    local name=a.name or path:match("([^/]+)%.xml$")
    assert(type(name)=="string" and #name<200,"invalid build name")
    main:SetMode("BUILD",false,name,xml)
    return {defer=2,extra={backup=backup,loaded=path}}
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
    return {defer=2}
end
handlers.config=function(a)
    local b=build();assert(#main.popups==0,"close the active PoB dialog first");assert(type(a.values)=="table","values object required")
    for k,v in pairs(a.values) do
        assert(type(k)=="string" and #k<150,"invalid config name")
        assert(type(v)=="boolean" or type(v)=="number" or (type(v)=="string" and #v<500),"config values must be scalar")
    end
    for k,v in pairs(a.values) do b.configTab.input[k]=v end
    b.configTab:BuildModList();b.modFlag=true;b.buildFlag=true
    return {defer=2}
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
function bridge:tick()
    local now=GetTime()
    if now-self.heartbeatAt>=1000 then
        self.heartbeatAt=now
        write(base.."heartbeat.json",assert(json.encode({pid=pid,version="0.1.1",time=os.time()})))
    end
    if self.pending then
        self.pending.frames=self.pending.frames-1
        if self.pending.frames<=0 then
            local p=self.pending;self.pending=nil
            local ok,r=pcall(snapshot)
            if ok and p.extra then for k,v in pairs(p.extra) do r[k]=v end end
            self:respond(p.id,ok,r)
        end
        return
    end
    local text=read(base.."request.json");if not text then return end
    local req=json.decode(text)
    if not req or req.id==self.last or req.pid~=pid then return end
    if type(req.id)~="string" or not req.id:match("^[a-f0-9]+$") or #req.id~=32 then return end
    self.last=req.id
    local ok,r=pcall(function()
        assert(handlers[req.command],"unknown bridge command")
        return handlers[req.command](req.args or {},req.id)
    end)
    if not ok then self:respond(req.id,false,r)
    elseif r.defer then self.pending={id=req.id,frames=r.defer,extra=r.extra}
    else self:respond(req.id,true,r.result) end
end
return bridge
