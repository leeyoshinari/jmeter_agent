# jmeter_agent
It can be only used with [MyPlatform](https://github.com/leeyoshinari/MyPlatform.git), and can't be used alone.

## Deploy
1. Clone Repository
   ```shell
   git clone https://github.com/leeyoshinari/jmeter_agent.git
   ```

2. Modify `config.conf`. Usually don't need to modify, unless you have special requirements.
   
3.  Package. Using `pyinstaller` to package python code. 
- (1) Enter folder, run:<br>
    ```shell
    pyinstaller --onefile --name=server server.py --hidden-import taskController --hidden-import common
    ```
- (2) modify `server.spec`, modify `pathex` to current folder, for example: `pathex=['/home/jmeter_agent']`.
- (3) Run:<br>
    ```shell
    pyinstaller server.spec
    ```
- (4) Copy `config.conf` to the `dist` folder, cmd: `cp config.conf dist/`
- (5) Enter `dist` folder, zip files, cmd: `zip jmeter_agent.zip server config.conf`
- (6) Upload zip file to [MyPlatform](https://github.com/leeyoshinari/MyPlatform.git)
- (7) Deploy jmeter_agent

NOTE: For Linux Server, the executable file packaged on the server of the CentOS system X86 architecture can only run on the server of the CentOS system X86 architecture; servers of other system and architecture need to be repackaged. <br>
