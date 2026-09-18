import subprocess,sys,time,json,urllib.request
p=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','18765','--no-access-log'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for i in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:18765/health',timeout=1) as r:
                data=json.load(r)
            assert data['live_collection'] is False
            print('HTTP health smoke PASS');break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('server startup failed')
finally:
    p.terminate();p.wait(timeout=5)
