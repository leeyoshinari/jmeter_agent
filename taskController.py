#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: leeyoshinari
import os
import time
import json
import threading
import traceback
import redis
import requests
import zipfile
from apscheduler.schedulers.background import BackgroundScheduler
from common import get_config, logger, get_ip

bean_shell_server_port = 15225


class Task(object):
    def __init__(self):
        self.IP = get_ip()
        self.status = 0     # 0 idle, 1 busy, -1 pending
        self.current_tps = 0
        self.task_id = None
        self.plan_id = None
        self.number_samples = 1
        self.start_time = 0
        self.redis_host = '127.0.0.1'
        self.redis_port = 6379
        self.redis_password = '123456'
        self.redis_db = 0
        self.jmeter_message = ''
        self.jmeter_message_stream = ''
        self.deploy_path = ''
        self.get_configure_from_server()

        self.jmeter_path = os.path.join(self.deploy_path, 'JMeter')
        self.jmeter_executor = os.path.join(self.jmeter_path, 'bin', 'jmeter')
        self.setprop_path = os.path.join(self.jmeter_path, 'setprop.bsh')
        self.file_path = os.path.join(self.deploy_path, 'jmeter_files')
        self.redis_client = redis.StrictRedis(host=self.redis_host, port=self.redis_port, password=self.redis_password,
                                              db=self.redis_db, decode_responses=True)

        self.check_env()
        self.write_setprop()
        self.modify_properties()
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.scheduler.add_job(self.register, 'interval', seconds=60, id='register_1')
        self.start_thread(self.task_subscribe, ())

    @property
    def set_status(self):
        return self.status

    @set_status.setter
    def set_status(self, value):
        self.status = value

    def start_thread(self, func, data):
        t = threading.Thread(target=func, args=data)
        t.deamon = True
        t.start()

    def check_env(self):
        if not os.path.exists(self.jmeter_path):
            logger.error(f'The Jmeter path: {self.jmeter_path} is not exist ~')
            raise Exception(f'The Jmeter path: {self.jmeter_path} is not exist ~')

        res = exec_cmd(f'{self.jmeter_executor} -v')
        if 'Copyright' not in res:
            logger.error(f'Not Found {self.jmeter_executor} ~')
            raise Exception(f'Not Found {self.jmeter_executor} ~')

        res = exec_cmd('whereis java')
        if len(res) < 10:
            logger.error('Not Found Java ~')
            raise Exception('Not Found Java ~')

        if not os.path.exists(self.file_path):
            os.mkdir(self.file_path)

    def write_setprop(self):
        try:
            if not os.path.exists(self.setprop_path):
                with open(self.setprop_path, 'w', encoding='utf-8') as f:
                    f.write('import org.apache.jmeter.util.JMeterUtils;\ngetprop(p){\n    return JMeterUtils.getPropDefault(p,"");\n}\n'
                            'setprop(p,v){\n    JMeterUtils.getJMeterProperties().setProperty(p, v);\n}\nsetprop(args[0], args[1]);')
                    logger.info('setprop.bsh is written success ~')
            else:
                logger.info('setprop.bsh has been exist ~')
        except:
            logger.error(traceback.format_exc())

    def modify_properties(self):
        properties_path = os.path.join(self.jmeter_path, 'bin', 'jmeter.properties')
        # _ = exec_cmd(f"sed -i 's|.*summariser.interval.*|summariser.interval=10|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*beanshell.server.port.*|beanshell.server.port={bean_shell_server_port}|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*beanshell.server.file.*|beanshell.server.file=../extras/startup.bsh|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*jmeter.save.saveservice.samplerData.*|jmeter.save.saveservice.samplerData=true|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*jmeter.save.saveservice.response_data.*|jmeter.save.saveservice.response_data=true|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*jmeter.save.saveservice.response_data.on_error.*|jmeter.save.saveservice.response_data.on_error=true|g' {properties_path}")
        _ = exec_cmd(f"sed -i 's|.*summariser.ignore_transaction_controller_sample_result.*|summariser.ignore_transaction_controller_sample_result=false|g' {properties_path}")
        _ = exec_cmd(f"sed -e 's/^M//g' {properties_path}")
        logger.info(f'Modify {properties_path} success ~')

    def modify_host_to_jmx(self, file_path):
        _ = exec_cmd(f"sed -i 's|.*<stringProp name=\"Argument.value\">WillBeReplaceToHost</stringProp>.*|<stringProp name=\"Argument.value\">{self.IP}</stringProp>|g' {file_path}")

    def get_configure_from_server(self):
        url = f'{get_config("address")}/register/first'
        post_data = {'type': 'jmeter-agent', 'host': self.IP, 'port': get_config('port')}
        while True:
            try:
                res = self.request_post(url, post_data)
                self.redis_host = res['redis']['host']
                self.redis_port = res['redis']['port']
                self.redis_password = res['redis']['password']
                self.redis_db = res['redis']['db']
                self.jmeter_message = res['jmeter_message']
                self.jmeter_message_stream = res['jmeter_message_stream']
                self.deploy_path = res['deploy_path']
                break
            except:
                logger.error(traceback.format_exc())
            time.sleep(1)

    def register(self):
        try:
            data = {'host': self.IP, 'port': get_config('port'), 'status': self.status, 'tps': self.current_tps}
            self.redis_client.set(name='jmeterServer_' + self.IP, value=json.dumps(data, ensure_ascii=False), ex=120)
            logger.info(f"Agent register successful, TPS: {self.current_tps}")
        except:
            logger.error(traceback.format_exc())

    @staticmethod
    def check_status(is_run=True):
        try:
            res = exec_cmd('ps -ef|grep jmeter |grep -v grep').strip()
            if res and is_run:  # whether is start
                return True
            elif not res and not is_run:    # whether is stop
                return True
            else:
                return False
        except:
            logger.error(traceback.format_exc())

    def send_message(self, task_type):
        try:
            data = {'host': self.IP, 'taskId': self.task_id, 'type': task_type}
            self.redis_client.xadd(self.jmeter_message_stream, {'data': json.dumps(data, ensure_ascii=False)}, maxlen=5)
            logger.debug(f"Send message successful, data: {data}")
        except:
            logger.error(traceback.format_exc())

    def parse_log(self, log_path):
        while not os.path.exists(log_path):
            time.sleep(2)

        position = 0
        last_time = time.time()
        logger.info(f'JMeter log path is {log_path}')
        with open(log_path, mode='r', encoding='utf-8') as f1:
            while True:
                line = f1.readline()
                if 'o.a.j.v.b.BackendListener:' in line and 'Worker ended' in line:
                    self.status = 0
                    self.stop_task()
                    break

                if 'Thread finished:' in line:
                    self.status = 0
                    self.stop_task()
                    break

                if time.time() - last_time > 120:
                    self.status = 0
                    self.stop_task()
                    break

                cur_position = f1.tell()  # record last position
                if cur_position == position:
                    time.sleep(2)
                    continue
                else:
                    position = cur_position
                    last_time = time.time()
                    time.sleep(2)
            logger.info(f'{self.task_id} has been stopped ~')
            if self.status > 0:
                self.stop_task()

    def download_log(self, task_id):
        jtl_path = os.path.join(self.file_path, task_id, task_id + '.jtl')
        jmeter_log_path = os.path.join(self.file_path, task_id, task_id + '.log')
        zip_file_path = os.path.join(self.file_path, task_id, task_id + '.zip')
        archive = zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED)
        if os.path.exists(jtl_path):
            archive.write(jtl_path, task_id + '.jtl')
        archive.write(jmeter_log_path, task_id + '.log')
        archive.close()
        logger.info(f'JMeter log file download success, filePath: {zip_file_path}')
        with open(zip_file_path, 'rb') as f:
            res = f.read()
        os.remove(zip_file_path)
        return res

    def download_file_to_path(self, url, file_path):
        with open(file_path, 'wb') as f:
            f.write(self.download_file_to_bytes(url))
        logger.info(f'Download file: {url} to {file_path} success ~')

    def download_file_to_bytes(self, url):
        res = requests.get(url)
        return res.content

    def unzip_file(self, source_path, target_path):
        f = zipfile.ZipFile(source_path)
        f.extractall(target_path)
        f.close()
        logger.info(f'unzip file: {source_path} to {target_path} success ~')

    def run_task(self, data):
        if self.check_status(is_run=True):
            self.kill_process()

        task_id = data.get('taskId')
        try:
            local_file_path = os.path.join(self.file_path, task_id + '.zip')
            target_file_path = os.path.join(self.file_path, task_id)
            self.download_file_to_path(data.get('filePath'), local_file_path)
            self.unzip_file(local_file_path, target_file_path)
            os.remove(local_file_path)
            if not os.path.exists(target_file_path):
                logger.error('Not Found file after unzip')
                return {'code': 1, 'msg': 'Not Found file after unzip'}
            jmx_files = [file for file in os.listdir(target_file_path) if file.endswith('.jmx')]
            if not jmx_files:
                logger.error('Not Found jmx file ~')
                return {'code': 1, 'msg': 'Not Found jmx file, please zip file again ~'}
            jmx_file_path = os.path.join(target_file_path, jmx_files[0])
            self.modify_host_to_jmx(jmx_file_path)
            log_path = os.path.join(target_file_path, task_id + '.log')
            jtl_file_path = os.path.join(target_file_path, task_id + '.jtl')
            if data.get('isDebug') == 1:
                cmd = f'nohup {self.jmeter_executor} -n -t {jmx_file_path} -l {jtl_file_path} -j {log_path} >/dev/null 2>&1 &'
            else:
                cmd = f'nohup {self.jmeter_executor} -n -t {jmx_file_path} -j {log_path} >/dev/null 2>&1 &'
            _ = exec_cmd(cmd)
            logger.info(f'Run JMeter success, shell: {cmd}')
            time.sleep(5)
            if self.check_status(is_run=True):
                self.scheduler.remove_job('register_1')
                self.status = 1
                self.task_id = str(task_id)
                self.number_samples = data.get('numberSamples')
                self.start_time = time.time()
                logger.info(f'{jmx_file_path} run successful, task id: {self.task_id}')
                self.start_thread(self.parse_log, (log_path,))
                self.scheduler.add_job(self.register, 'interval', seconds=5, id='register_1')
                self.send_message('run_task')
            else:
                logger.error(f'{jmx_file_path} run failure, task id: {task_id}')
        except:
            logger.error(traceback.format_exc())

    def stop_task(self):
        if self.check_status(is_run=True):
            try:
                self.kill_process()
                time.sleep(5)
                if self.check_status(is_run=False):
                    self.status = 0
                    self.current_tps = 0
                    self.number_samples = 1
                    self.scheduler.remove_job('register_1')
                    self.scheduler.add_job(self.register, 'interval', seconds=60, id='register_1')
                    logger.info('Task stop successful ~')
                else:
                    logger.error('Task stop failure ~')
                    return False
            except:
                logger.error(traceback.format_exc())
                return False
        else:
            self.status = 0
            self.current_tps = 0
            self.number_samples = 1
            logger.error('Task has stopped ~')

        self.send_message('stop_task')

    @staticmethod
    def kill_process():
        try:
            _ = exec_cmd("ps -ef|grep jmeter |grep -v grep |awk '{print $2}' |xargs kill -9")
            _ = exec_cmd("ps -ef|grep java |grep -v grep |grep jmx |awk '{print $2}' |xargs kill -9")
        except:
            logger.error(traceback.format_exc())

    def task_subscribe(self):
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(self.jmeter_message)
        for message in pubsub.listen():
            logger.info(f"Subscribe Message: {message}")
            if message['type'] == 'message':
                data = json.loads(message['data'].decode('utf-8'))
                if self.IP in data['host']:
                    if data['cmd'] == 'startTask' and self.status != 1:
                        self.run_task(data)
                    if data['cmd'] == 'stopTask' and self.task_id == data['taskId']:
                        self.stop_task()
                    if data['cmd'] == 'changeTPS' and self.task_id == data['taskId']:
                        self.change_tps(data['tps'])

    def change_tps(self, tps):
        try:
            cmd = f'java -jar {self.jmeter_path}/lib/bshclient.jar localhost {bean_shell_server_port} {self.setprop_path} throughput {tps}'
            _ = exec_cmd(cmd)
            logger.info(f'Change TPS to {tps}, CMD: {cmd}')
        except:
            logger.error(traceback.format_exc())

    def request_post(self, url, post_data):
        header = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json; charset=UTF-8"}
        try:
            res = requests.post(url=url, json=post_data, headers=header)
            logger.info(f"The result of request is {res.content.decode('unicode_escape')}")
            if res.status_code == 200:
                response_data = json.loads(res.content.decode('unicode_escape'))
                if response_data['code'] == 0:
                    return response_data['data']
                else:
                    logger.error(response_data['msg'])
                    raise Exception(response_data['msg'])
            else:
                raise Exception(f'{url} - status_code: - {res.status_code}')
        except:
            logger.error(traceback.format_exc())
            raise


def exec_cmd(cmd):
    try:
        with os.popen(cmd) as p:
            result = p.read()
        return result
    except:
        raise