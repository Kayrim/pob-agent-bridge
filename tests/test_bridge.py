import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from pob_bridge import cli as b


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('POB_TEST_TMPDIR'))
        self.root=Path(self.tmp.name)
        self.patches=[patch.object(b,'ROOT',self.root),patch.object(b,'RUNTIME',self.root/'agent-bridge/runtime')]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_install_uninstall_preserves_original(self):
        original='-- fixture\n'+b.ANCHOR+'-- untouched\n'
        launch=self.root/'Launch.lua';launch.write_text(original,encoding='utf-8')
        self.assertTrue(b.install()['changed'])
        self.assertFalse(b.install()['changed'])
        self.assertEqual(launch.read_text().count(b.HOOK),1)
        backups=list(b.RUNTIME.glob('Launch.original.*.lua'))
        self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_text(),original)
        self.assertTrue((self.root/'agent-bridge/live.lua').exists())
        b.uninstall()
        self.assertEqual(launch.read_text(),original)
    def test_install_refuses_unknown_hook_without_copying(self):
        launch=self.root/'Launch.lua';launch.write_text(b.MARKER+'-- unexpected\n')
        before=launch.read_bytes()
        with self.assertRaisesRegex(RuntimeError,'differs'):b.install()
        self.assertEqual(launch.read_bytes(),before)
        self.assertFalse(b.RUNTIME.exists())
    def test_workspace_boundaries_and_symlinks(self):
        self.assertEqual(b.workspace_path('build.xml'),self.root/'build.xml')
        for path in ('../outside.xml','wrong.txt',str(self.root.parent/'outside.xml')):
            with self.assertRaises(ValueError):b.workspace_path(path)
        outside=self.root.parent/'outside-target'
        try:
            (self.root/'escape').symlink_to(outside,target_is_directory=True)
        except OSError:return  # Windows may require Developer Mode for symlinks.
        with self.assertRaises(ValueError):b.workspace_path('escape/build.xml')
    def test_schema_rejects_partial_invalid_mutations(self):
        with patch.object(b,'request') as request:
            for args in ({'tree':True},{'tree':0},{'tree':1,'typo':2},{'view':'BAD'}):
                with self.assertRaises(ValueError):b.call_tool('pob_select',args)
            for value in ([],None,float('nan'),{'nested':'object'}):
                with self.assertRaises(ValueError):b.call_tool('pob_config',{'values':{'x':value}})
            request.assert_not_called()
    def test_pending_request_is_not_overwritten(self):
        b.RUNTIME.mkdir(parents=True)
        req={'id':'a'*32,'pid':42,'command':'load','args':{}}
        (b.RUNTIME/'heartbeat.json').write_text(json.dumps({'pid':42}))
        (b.RUNTIME/'request.json').write_text(json.dumps(req))
        before=(b.RUNTIME/'request.json').read_bytes()
        self.assertTrue(b.pending()['pending'])
        with self.assertRaisesRegex(RuntimeError,'unknown outcome'):b.request('status',timeout=.1)
        self.assertEqual((b.RUNTIME/'request.json').read_bytes(),before)
        (b.RUNTIME/'response.json').write_text(json.dumps({'id':'a'*32,'ok':True,'result':{}}))
        self.assertFalse(b.pending()['pending'])
    def test_stale_gui_rejected_before_submission(self):
        b.RUNTIME.mkdir(parents=True)
        p=b.RUNTIME/'heartbeat.json';p.write_text(json.dumps({'pid':42}))
        os.utime(p,(time.time()-30,time.time()-30))
        with self.assertRaisesRegex(RuntimeError,'fresh'):b.request('select',{'tree':1},timeout=.1)
        self.assertFalse((b.RUNTIME/'request.json').exists())
    def test_mcp_protocol_and_schema_errors(self):
        lines=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
               {'jsonrpc':'2.0','method':'notifications/initialized'},
               {'jsonrpc':'2.0','id':2,'method':'tools/list'},
               {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'pob_config','arguments':{'values':{'x':[]}}}},
               {'jsonrpc':'2.0','id':4,'method':'not-a-method'},
               {'jsonrpc':'2.0','id':5,'method':'ping','params':[]},
               {'jsonrpc':'2.0','id':6,'method':'ping'}]
        source=io.StringIO('\n'.join(json.dumps(x) for x in lines)+'\n{bad\n')
        target=io.StringIO()
        with patch.object(sys,'stdin',source),patch.object(sys,'stdout',target):b.mcp()
        replies=[json.loads(x) for x in target.getvalue().splitlines()]
        self.assertEqual([x['id'] for x in replies],[1,2,3,4,5,6,None])
        self.assertEqual(len(replies[1]['result']['tools']),8)
        self.assertTrue(replies[2]['result']['isError'])
        self.assertEqual(replies[3]['error']['code'],-32601)
        self.assertEqual(replies[4]['error']['code'],-32602)
        self.assertEqual(replies[-1]['error']['code'],-32700)


@unittest.skipUnless(os.environ.get('POB_TEST_DIR') and os.name=='nt','Set POB_TEST_DIR for real Windows engine checks')
class NativeEngineTests(unittest.TestCase):
    def test_native_live_handlers_in_isolated_engine(self):
        """Exercise the real Lua mailbox against native objects, without a GUI."""
        root=Path(os.environ['POB_TEST_DIR']).resolve()
        runtime=root/'agent-bridge/runtime';runtime.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as tmp:
            folder=Path(tmp)
            (folder/'agent-bridge/runtime').mkdir(parents=True)
            (folder/'fixture.xml').write_bytes((Path(__file__).resolve().parents[1]/'examples/minimal.xml').read_bytes())
            script='''
local testRoot=TEST_ROOT
GetScriptPath=function() return testRoot end
GetTime=function() return 1000 end
local bridge=assert(loadfile(BRIDGE_SOURCE))(launch.main)
local json=require('dkjson')
bridge:tick()
local function read(p)local f=assert(io.open(p,'rb'));local t=f:read('*a');f:close();return json.decode(t) end
local pid=read(testRoot..'/agent-bridge/runtime/heartbeat.json').pid
local counter=0
local function request(command,args)
 counter=counter+1
 local f=assert(io.open(testRoot..'/agent-bridge/runtime/request.json','wb'))
 f:write(json.encode({id=string.format('%032x',counter),pid=pid,command=command,args=args or {}}));f:close()
 bridge:tick();runCallback('OnFrame');bridge:tick();runCallback('OnFrame');bridge:tick()
 return read(testRoot..'/agent-bridge/runtime/response.json')
end
assert(request('load',{path=testRoot..'/fixture.xml'}).ok,'load failed')
local selected=request('select',{tree=1,skills=1,items=1,configSet=1,mainSkillGroup=1,view='CALCS'})
assert(selected.ok and selected.result.configSet==1,'select failed: '..json.encode(selected))
assert(#selected.result.configSets>0,'missing config sets')
local before=request('status').result
assert(not request('select',{tree=999,skills=1}).ok,'invalid tree accepted')
local after=request('status').result
assert(before.tree==after.tree and before.skills==after.skills,'invalid selection mutated state')
assert(request('config',{values={enemyIsBoss='Pinnacle'}}).ok,'config failed')
assert(request('export',{path=testRoot..'/export.xml'}).ok,'export failed')
assert(not request('export',{path=testRoot..'/export.xml'}).ok,'export overwrote file')
assert(not request('export',{path='../outside.xml'}).ok,'path escape accepted')
print('LIVE_HANDLERS_OK')
'''
            source=folder/'test.lua'
            source.write_text('TEST_ROOT='+json.dumps(folder.as_posix())+'\nBRIDGE_SOURCE='+json.dumps((Path(__file__).resolve().parents[1]/'pob_bridge/live.lua').as_posix())+'\n'+script,encoding='utf-8')
            bootstrap='''import sys,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('engine',sys.argv[2]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.run(m.prelude()+'\\n'+Path(sys.argv[3]).read_text(encoding='utf-8'))
'''
            process=subprocess.run([sys.executable,'-c',bootstrap,str(root),str(Path(__file__).resolve().parents[1]/'pob_bridge/engine.py'),str(source)],capture_output=True,text=True,timeout=60)
            self.assertEqual(process.returncode,0,process.stderr[-2500:])
            self.assertIn('LIVE_HANDLERS_OK',process.stdout)

    def test_native_calculation_and_mcp(self):
        root=Path(os.environ['POB_TEST_DIR']).resolve()
        runtime=root/'agent-bridge/runtime';runtime.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix='.xml',dir=runtime,delete=False) as f:
            source=Path(f.name)
            f.write((Path(__file__).resolve().parents[1]/'examples/minimal.xml').read_bytes())
        try:
            legacy=source.with_name(source.stem+'-legacy.xml')
            legacy.write_text(source.read_text().replace('targetVersion="3_0"','targetVersion="2_6"'),encoding='utf-8')
            request={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'pob_calculate','arguments':{'path':str(source)}}}
            bad={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'pob_calculate','arguments':{'path':str(source),'tree':999}}}
            outdated={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'pob_calculate','arguments':{'path':str(legacy)}}}
            result=subprocess.run([sys.executable,'-m','pob_bridge','--pob-dir',str(root),'mcp'],input='\n'.join(json.dumps(x) for x in (request,bad,outdated))+'\n',text=True,capture_output=True,timeout=65,check=True)
            replies=[json.loads(x) for x in result.stdout.splitlines()]
            self.assertNotIn('isError',replies[0]['result'],result.stdout[-2000:])
            value=json.loads(replies[0]['result']['content'][0]['text'])
            self.assertEqual(value['backend'],'isolated-native-engine')
            self.assertEqual(value['level'],10)
            self.assertGreater(value['stats']['Life'],0)
            self.assertGreater(value['stats']['CombinedDPS'],0)
            self.assertTrue(replies[1]['result']['isError'])
            self.assertTrue(replies[2]['result']['isError'])
            self.assertIn('requires a dialog',replies[2]['result']['content'][0]['text'])
        finally:
            source.unlink(missing_ok=True)
            legacy.unlink(missing_ok=True)


if __name__=='__main__':unittest.main()
