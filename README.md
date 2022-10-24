# jmeter_agent

## Usage
1. Clone performance_monitor
   ```shell
   git clone https://github.com/leeyoshinari/jmeter_agent.git
   ```

2. Deploy InfluxDB, installation steps on CentOS are as follows:<br>
    (1) Download and install<br>
        `wget https://dl.influxdata.com/influxdb/releases/influxdb-1.8.3.x86_64.rpm` <br>
        `yum localinstall influxdb-1.8.3.x86_64.rpm` <br>
    (2) Start<br>
        `systemctl enable influxdb` <br>
        `systemctl start influxdb` <br>
    (3) Modify configuration<br>
         `vim /etc/influxdb/influxdb.conf` <br>
         Around line 256, modify port: `bind-address = ":8086"` <br>
         Around line 265, log disable: `log-enabled = false` <br>
         Restart InfluxDB <br>
    (4) Create database<br>
        `create database test` <br>
        `use test` <br>
        `create user root with password '123456'` create user and password <br>
        `grant all privileges on test to root` grant privileges <br>
   
3. Modify the configuration files `config.ini`.<br>

4. Check the version of `sysstat`. Respectively use commands `iostat -V` and `pidstat -V`, the version of `12.4.0` has been tested, if not, please [click me](http://sebastien.godard.pagesperso-orange.fr/download.html) to download it.

5. Run `server.py`.
   ```shell
   nohup python3 server.py &
   ```
   
## Package
Using `pyinstaller` to package python code. After packaging, it can be quickly deployed on other Servers without installing python3.7+ and third-party packages.<br>
Before packaging, you must ensure that the python code can run normally.<br>
- (1) Enter folder, run:<br>
    ```shell
    pyinstaller -F server.py -p taskController.py -p common.py -p __init__.py --hidden-import taskController --hidden-import common
    ```
- (2) Copy `config.conf` to the `dist` folder, cmd: `cp config.conf dist/`
- (3) Enter `dist` folder, zip files, cmd: `zip jmeter_agent.zip server config.conf`
- (4) Upload zip file to [MyPlatform](https://github.com/leeyoshinari/MyPlatform.git)
- (5) Deploy jmeter_agent

   NOTE: Since it runs on the server to be monitored, the executable file packaged on the server of the CentOS system X86 architecture can only run on the server of the CentOS system X86 architecture; servers of other system and architecture need to be repackaged. <br>
