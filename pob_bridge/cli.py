"""Fast local commands and optional MCP stdio tools for the live PoB bridge."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import shutil
import sys
import time
import uuid
from . import __version__

PACKAGE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('POB_DIR', '.')).resolve()
RUNTIME=ROOT/'agent-bridge'/'runtime'
MARKER='\t-- BEGIN LOCAL POB AGENT BRIDGE\n'
HOOK='''\t-- BEGIN LOCAL POB AGENT BRIDGE
\tif not self.agentBridgeTried then
\t\tself.agentBridgeTried = true
\t\tlocal loader = loadfile("agent-bridge/live.lua")
\t\tif loader then
\t\t\tlocal ok, value = pcall(loader, self.main)
\t\t\tif ok then self.agentBridge = value else ConPrintf("Agent bridge: %s", tostring(value)) end
\t\tend
\tend
\tif self.agentBridge then
\t\tlocal ok, err = pcall(self.agentBridge.tick, self.agentBridge)
\t\tif not ok then ConPrintf("Agent bridge: %s", tostring(err)); self.agentBridge = nil end
\tend
\t-- END LOCAL POB AGENT BRIDGE
'''
ANCHOR='\tself.devModeAlt = self.devMode and IsKeyDown("ALT")\n'

def workspace_path(value: str, suffix='.xml') -> Path:
    p=Path(value)
    if not p.is_absolute(): p=ROOT/p
    p=p.resolve()
    if not p.is_relative_to(ROOT) or (suffix and p.suffix.lower()!=suffix):
        raise ValueError('Path must be an XML file inside the PoB workspace')
    # Resolve symlinks before handing the verified path to the Lua side.
    return p

def install() -> dict:
    launch=ROOT/'Launch.lua'
    text=launch.read_text(encoding='utf-8')
    if MARKER in text and HOOK not in text: raise RuntimeError('Bridge hook differs; refusing to overwrite it')
    if MARKER not in text and text.count(ANCHOR)!=1: raise RuntimeError('PoB frame hook changed; manual compatibility review needed')
    RUNTIME.mkdir(parents=True,exist_ok=True)
    for name in ('live.lua','calculate.lua'):
        target=ROOT/'agent-bridge'/name
        if target.resolve()!=(PACKAGE/name).resolve():shutil.copy2(PACKAGE/name,target)
    if MARKER in text:
        return {'installed':True,'changed':False,'restartRequired':True}
    digest=hashlib.sha256(launch.read_bytes()).hexdigest()
    backup=RUNTIME/f'Launch.original.{digest}.lua'
    if not backup.exists(): backup.write_bytes(launch.read_bytes())
    launch.write_text(text.replace(ANCHOR,HOOK+ANCHOR,1),encoding='utf-8',newline='\n')
    return {'installed':True,'changed':True,'backup':str(backup),'restartRequired':True}

def uninstall() -> dict:
    launch=ROOT/'Launch.lua';text=launch.read_text(encoding='utf-8')
    if MARKER not in text:return {'installed':False,'changed':False}
    if text.count(HOOK)!=1:raise RuntimeError('Modified hook; refusing to remove unrelated code')
    launch.write_text(text.replace(HOOK,'',1),encoding='utf-8',newline='\n')
    return {'installed':False,'changed':True,'restartRequired':True}

def heartbeat(max_age=5) -> dict | None:
    p=RUNTIME/'heartbeat.json'
    try:
        if max_age is not None and time.time()-p.stat().st_mtime>max_age:return None
        return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):return None

@contextlib.contextmanager
def locked(timeout: float):
    RUNTIME.mkdir(parents=True,exist_ok=True)
    path=RUNTIME/'client.lock';deadline=time.monotonic()+timeout
    while True:
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            os.write(fd,str(os.getpid()).encode());os.close(fd);break
        except FileExistsError:
            if time.monotonic()>=deadline:raise TimeoutError('Another bridge client owns client.lock; no request was submitted')
            time.sleep(.05)
    try:yield
    finally:path.unlink(missing_ok=True)

def request(command: str,args: dict | None=None,timeout=15.0) -> dict:
    args=dict(args or {})
    if command in ('load','export'):args['path']=workspace_path(args['path']).as_posix()
    with locked(timeout):
        owner=heartbeat()
        if not owner:raise RuntimeError('No fresh live heartbeat. Install/restart PoB, then keep its window active. Use pob_calculate for unattended work; inspect pob_pending before retrying a timed-out mutation.')
        previous=pending()
        if previous.get('pending'):raise RuntimeError('A previous request has unknown outcome. Inspect pob_pending and let PoB service it before submitting another request.')
        identity=uuid.uuid4().hex
        req={'id':identity,'pid':owner['pid'],'command':command,'args':args}
        temp=RUNTIME/f'{identity}.tmp'
        temp.write_text(json.dumps(req),encoding='utf-8')
        temp.replace(RUNTIME/'request.json')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:reply=json.loads((RUNTIME/'response.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):reply={}
            if reply.get('id')==identity:
                if not reply['ok']:raise RuntimeError(reply.get('error','PoB rejected the request'))
                return reply['result']
            time.sleep(.025)
        raise TimeoutError(f'Request {identity} outcome unknown. Inspect response.json/status before retrying a mutation.')

def launch(keep_alive=False) -> dict:
    install()
    existing=heartbeat()
    if existing:return {'alreadyRunning':True,**existing}
    process=subprocess.Popen([str(ROOT/'Path of Building.exe')],cwd=ROOT)
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        owner=heartbeat()
        if owner:
            result={'startedPid':process.pid,**owner}
            if keep_alive:
                print(json.dumps(result),flush=True)
                process.wait()
                return {'exited':True,'exitCode':process.returncode}
            return result
        if process.poll() is not None:raise RuntimeError(f'PoB exited with {process.returncode}')
        time.sleep(.15)
    raise TimeoutError('PoB launched but bridge has no heartbeat; inspect its startup state. Existing windows were not closed.')

def calculate(args: dict) -> dict:
    """Evaluate with the installed engine without touching the live GUI build."""
    args=dict(args);args['path']=workspace_path(args['path']).as_posix()
    if Path(args['path']).stat().st_size>16*1024*1024:raise ValueError('Build XML exceeds 16 MiB')
    folder=RUNTIME/'calculations';folder.mkdir(parents=True,exist_ok=True)
    identity=uuid.uuid4().hex
    source=folder/f'{identity}.request.json';result=folder/f'{identity}.result.json'
    source.write_text(json.dumps(args),encoding='utf-8')
    env=os.environ.copy();env['POB_BRIDGE_REQUEST']=str(source);env['POB_BRIDGE_RESULT']=str(result)
    try:
        completed=subprocess.run([sys.executable,str(PACKAGE/'engine.py'),str(ROOT)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=60)
        if completed.returncode or not result.exists():raise RuntimeError((completed.stderr or completed.stdout)[-3000:] or 'Native calculation produced no result')
        return json.loads(result.read_text(encoding='utf-8'))
    finally:
        source.unlink(missing_ok=True);result.unlink(missing_ok=True)


def pending() -> dict:
    def read(name):
        try:return json.loads((RUNTIME/name).read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    req,reply=read('request.json'),read('response.json')
    owner=heartbeat(max_age=None) or {}
    relevant=bool(req and req.get('pid')==owner.get('pid'))
    return {'pending':relevant and req.get('id')!=reply.get('id'),
            'request':{k:req.get(k) for k in ('id','pid','command')} if relevant else None,
            'response':reply if relevant and reply.get('id')==req.get('id') else None}


def health() -> dict:
    try:text=(ROOT/'Launch.lua').read_text(encoding='utf-8')
    except OSError:text=''
    return {'pobDirectory':str(ROOT),'validInstallation':bool(text and (ROOT/'lua51.dll').exists()),
            'hookInstalled':HOOK in text,'liveHeartbeatFresh':heartbeat() is not None,
            'heartbeat':heartbeat(max_age=None),'pending':pending()['pending'],
            'testedPoBVersion':'2.67.2','platform':'Windows x64; Python x64',
            'advice':'Use pob_calculate without a GUI. Live tools require a foreground PoB window.'}

TOOLS=[
    {'name':'pob_health','description':'Start here: inspect installation, removable hook, fresh GUI heartbeat and pending requests. No running GUI required.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
    {'name':'pob_pending','description':'Inspect outcome of the last live request after a timeout. Never blindly retry a mutation with unknown outcome.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
    {'name':'pob_calculate','description':'Calculate a workspace XML with the installed native PoB engine in isolation; works with GUI closed or idle and leaves it unchanged.','inputSchema':{'type':'object','properties':{'path':{'type':'string'},'tree':{'type':'integer','minimum':1},'skills':{'type':'integer','minimum':1},'items':{'type':'integer','minimum':1},'configSet':{'type':'integer','minimum':1},'mainSkillGroup':{'type':'integer','minimum':1},'values':{'type':'object','additionalProperties':{'type':['string','number','boolean']}}},'required':['path'],'additionalProperties':False}},
    {'name':'pob_status','description':'Read current live PoB build, stages, gems and calculated stats.','inputSchema':{'type':'object','properties':{},'additionalProperties':False}},
    {'name':'pob_load','description':'Load a workspace XML in live PoB; first preserve the current build in runtime/before-ID.xml.','inputSchema':{'type':'object','properties':{'path':{'type':'string'},'name':{'type':'string'}},'required':['path'],'additionalProperties':False}},
    {'name':'pob_select','description':'Select existing tree, skill set, item set, main skill group or app view; returns recalculated stats.','inputSchema':{'type':'object','properties':{'tree':{'type':'integer','minimum':1},'skills':{'type':'integer','minimum':1},'items':{'type':'integer','minimum':1},'configSet':{'type':'integer','minimum':1},'mainSkillGroup':{'type':'integer','minimum':1},'view':{'enum':['TREE','SKILLS','ITEMS','CALCS','CONFIG','NOTES','IMPORT']}},'additionalProperties':False}},
    {'name':'pob_config','description':'Set scalar PoB configuration inputs, then recalculate. Uses installed game data.','inputSchema':{'type':'object','properties':{'values':{'type':'object','additionalProperties':{'type':['string','number','boolean']}}},'required':['values'],'additionalProperties':False}},
    {'name':'pob_export','description':'Export current live build to a NEW XML file inside the workspace; refuses overwriting.','inputSchema':{'type':'object','properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}},
]

for tool in TOOLS:
    readonly=tool['name'] in ('pob_health','pob_pending','pob_status','pob_calculate')
    tool['annotations']={'readOnlyHint':readonly,'destructiveHint':not readonly,
                         'idempotentHint':readonly,'openWorldHint':False}


def validate_arguments(value, schema, path='arguments'):
    kind=schema.get('type')
    options=kind if isinstance(kind,list) else [kind]
    matches={'object':isinstance(value,dict),'string':isinstance(value,str),
             'integer':isinstance(value,int) and not isinstance(value,bool),
             'number':isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value),
             'boolean':isinstance(value,bool),None:True}
    if not any(matches.get(k,False) for k in options):raise ValueError(f'{path}: expected {kind}')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(f'{path}: unsupported value')
    if 'minimum' in schema and value<schema['minimum']:raise ValueError(f'{path}: below minimum')
    if isinstance(value,dict):
        props=schema.get('properties',{})
        for key in schema.get('required',[]):
            if key not in value:raise ValueError(f'{path}: missing {key}')
        for key,item in value.items():
            if not isinstance(key,str):raise ValueError(f'{path}: keys must be strings')
            child=props.get(key,schema.get('additionalProperties',{}))
            if child is False:raise ValueError(f'{path}: unknown field {key}')
            if isinstance(child,dict):validate_arguments(item,child,f'{path}.{key}')


def call_tool(name, arguments):
    definition=next((t for t in TOOLS if t['name']==name),None)
    if definition is None:raise ValueError('Unknown tool')
    validate_arguments(arguments,definition['inputSchema'])
    if name=='pob_health':return health()
    if name=='pob_pending':return pending()
    if name=='pob_calculate':return calculate(arguments)
    return request(name.removeprefix('pob_'),arguments)

def mcp():
    """MCP JSON-RPC over newline-delimited stdin/stdout; no server socket."""
    for stream in (sys.stdin,sys.stdout):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    for line in sys.stdin:
        identity=None
        try:
            try:msg=json.loads(line)
            except ValueError:
                print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Parse error'}}),flush=True);continue
            if not isinstance(msg,dict) or msg.get('jsonrpc')!='2.0' or not isinstance(msg.get('method'),str):
                print(json.dumps({'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}),flush=True);continue
            identity=msg.get('id');method=msg.get('method');params=msg.get('params',{})
            if identity is None:continue
            if not isinstance(params,dict):raise ValueError('params must be an object')
            if method=='initialize':
                requested=params.get('protocolVersion')
                supported=('2024-11-05','2025-03-26','2025-06-18','2025-11-25')
                result={'protocolVersion':requested if requested in supported else supported[-1],'capabilities':{'tools':{}},'serverInfo':{'name':'pob-agent-bridge','version':__version__}}
            elif method=='ping':result={}
            elif method=='tools/list':result={'tools':TOOLS}
            elif method=='tools/call':
                name=params.get('name','')
                if name not in {t['name'] for t in TOOLS}:raise ValueError('Unknown tool')
                try:
                    value=call_tool(name,params.get('arguments',{}))
                    result={'content':[{'type':'text','text':json.dumps(value)}]}
                except Exception as exc:result={'content':[{'type':'text','text':str(exc)}],'isError':True}
            else:
                print(json.dumps({'jsonrpc':'2.0','id':identity,'error':{'code':-32601,'message':'Method not found'}}),flush=True);continue
            print(json.dumps({'jsonrpc':'2.0','id':identity,'result':result}),flush=True)
        except Exception as exc:
            print(json.dumps({'jsonrpc':'2.0','id':identity,'error':{'code':-32602,'message':str(exc)}}),flush=True)

def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pob-dir',default=os.environ.get('POB_DIR'),help='Writable Windows PoB installation directory; or set POB_DIR')
    parser.add_argument('command',choices=['install','uninstall','launch','health','pending','status','load','select','config','export','calculate','mcp'])
    parser.add_argument('path',nargs='?');parser.add_argument('--name')
    parser.add_argument('--tree',type=int);parser.add_argument('--skills',type=int);parser.add_argument('--items',type=int)
    parser.add_argument('--config-set',type=int);parser.add_argument('--main-skill-group',type=int);parser.add_argument('--view');parser.add_argument('--values',help='JSON object for config')
    parser.add_argument('--keep-alive',action='store_true',help='Keep launcher alive while PoB is running (for process-managed agent shells)')
    a=parser.parse_args()
    global ROOT,RUNTIME
    if not a.pob_dir:parser.error('--pob-dir or POB_DIR is required')
    ROOT=Path(a.pob_dir).expanduser().resolve();RUNTIME=ROOT/'agent-bridge'/'runtime'
    if not (ROOT/'Launch.lua').is_file():parser.error('PoB directory must contain Launch.lua (installed Community build)')
    if a.command=='mcp':mcp();return
    try:
        if a.command=='launch':value=launch(a.keep_alive)
        elif a.command in ('install','uninstall','health','pending'):value=globals()[a.command]()
        else:
            args={}
            if a.command in ('load','export','calculate'):
                if not a.path:parser.error('path is required')
                args['path']=a.path
            if a.name:args['name']=a.name
            if a.command=='select':
                args={k:v for k,v in {'tree':a.tree,'skills':a.skills,'items':a.items,'configSet':a.config_set,'mainSkillGroup':a.main_skill_group,'view':a.view}.items() if v is not None}
            if a.command=='config':args={'values':json.loads(a.values or '{}')}
            if a.command=='calculate':
                args.update({k:v for k,v in {'tree':a.tree,'skills':a.skills,'items':a.items,'configSet':a.config_set,'mainSkillGroup':a.main_skill_group}.items() if v is not None})
                args['values']=json.loads(a.values or '{}')
            value=call_tool('pob_'+a.command,args)
        print(json.dumps(value,indent=2))
    except Exception as exc:print(json.dumps({'error':str(exc)}));sys.exit(1)

if __name__=='__main__':cli()
