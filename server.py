#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: leeyoshinari
import os
import asyncio
import traceback
from aiohttp import web
from common import get_config
from taskController import Task

task = Task()
HOST = task.IP
PID = os.getpid()
with open('pid', 'w', encoding='utf-8') as f:
    f.write(str(PID))


async def index(request):
    return web.Response(body=f'The server system version is')


async def download_file(request):
    """
     Get the list of monitoring ports
    :param request:
    :return:
    """
    task_id = request.match_info['task_id']
    return web.Response(content_type='application/octet-stream', headers={'Content-Disposition': f'attachment;filename={task_id}.zip'}, body=task.download_log(task_id))


async def main():
    app = web.Application()

    app.router.add_route('GET', '/', index)
    app.router.add_route('GET', '/download/{task_id}', download_file)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, get_config('port'))
    await site.start()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.run_forever()
