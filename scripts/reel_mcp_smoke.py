"""Exercise the real stdio MCP protocol against a running local studio."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8767)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    server=StdioServerParameters(command=sys.executable, args=[str(root/'local_studio/reel_mcp.py'),'--port',str(args.port)])
    history=[]
    async with stdio_client(server) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            names=[t.name for t in (await session.list_tools()).tools]
            assert {'save_reel','render_reel','job_status'} <= set(names)
            async def call(name, data=None):
                result=await session.call_tool(name, data or {})
                if result.isError: raise RuntimeError(str(result.content))
                value=result.structuredContent or json.loads(result.content[0].text)
                history.append({'tool':name,'ok':True})
                return value
            async def wait(job):
                deadline=time.monotonic()+600
                while job['status'] in ('queued','running'):
                    if time.monotonic()>deadline: raise TimeoutError('MCP job timeout')
                    await asyncio.sleep(.7)
                    job=await call('job_status',{'job_id':job['id']})
                if job['status']!='done': raise RuntimeError(job['message'])
                return job['result']
            await call('studio_status')
            project=(await wait(await call('import_video',{'path':str(args.video.resolve())})))['project']
            plan=json.loads(args.plan.read_text(encoding='utf-8-sig'))
            await call('save_reel',{'project_id':project['id'],'plan':plan})
            saved=await call('get_project',{'project_id':project['id']})
            assert len(saved['reel']['clips'])==len(plan['clips'])
            result=await wait(await call('render_reel',{'project_id':project['id']}))
            report={'protocol':'MCP stdio','tools':names,'calls':history,'project_id':project['id'],'render':result}
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'project_id':project['id'],'render':result},ensure_ascii=False))

if __name__=='__main__': asyncio.run(main())
