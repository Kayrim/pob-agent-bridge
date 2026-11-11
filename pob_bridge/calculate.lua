-- Isolated native-engine calculation. Invoked through the matching headless harness.
local json=require("dkjson")
local function read(path)local f=assert(io.open(path,"rb"));local s=f:read("*a");f:close();return s end
local req=assert(json.decode(read(assert(os.getenv("POB_BRIDGE_REQUEST")))))
loadBuildFromXML(read(req.path),req.name or "Agent calculation")
assert(launch.main.mode=="BUILD" and #launch.main.popups==0,"PoB requires a dialog; open and resave this XML with the installed PoB version before isolated calculation")
if req.tree then assert(build.treeTab.specList[req.tree],"unknown tree");build.treeTab:SetActiveSpec(req.tree) end
if req.skills then assert(build.skillsTab.skillSets[req.skills],"unknown skill set");build.skillsTab:SetActiveSkillSet(req.skills) end
if req.items then assert(build.itemsTab.itemSets[req.items],"unknown item set");build.itemsTab:SetActiveItemSet(req.items) end
if req.configSet then assert(build.configTab.configSets[req.configSet],"unknown config set");build.configTab:SetActiveConfigSet(req.configSet) end
if req.mainSkillGroup then assert(build.skillsTab.socketGroupList[req.mainSkillGroup],"unknown main skill group");build.mainSocketGroup=req.mainSkillGroup end
for k,v in pairs(req.values or {}) do build.configTab.input[k]=v end
build.configTab:BuildModList();build.buildFlag=true;runCallback("OnFrame");runCallback("OnFrame")
local r={backend="isolated-native-engine",pobVersion=launch.versionNumber,latestTreeVersion=latestTreeVersion,level=build.characterLevel,configSet=build.configTab.activeConfigSetId,tree=build.treeTab.activeSpec,skills=build.skillsTab.activeSkillSetId,items=build.itemsTab.activeItemSetId,points={build.spec:CountAllocNodes()},stats={}}
for k,v in pairs(build.calcsTab.mainOutput) do
    if type(v)=="number" and v==v and v~=math.huge and v~=-math.huge then r.stats[k]=v end
end
local f=assert(io.open(assert(os.getenv("POB_BRIDGE_RESULT")),"wb"));f:write(assert(json.encode(r)));f:close()
