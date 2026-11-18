import network,requests,time,machine
from lib.hydra.config import Config
c=Config()
w=network.WLAN(network.STA_IF)
w.active(True)
w.connect(c['wifi_ssid'],c['wifi_pass'])
while not w.isconnected():time.sleep(1)
r=requests.get('https://raw.githubusercontent.com/szuszjan/szuszjan.github.io/ccr-7347e944-2ijb9a/microhydra-apps/apps/AppInstaller.py')
open('/apps/AppInstaller.py','w').write(r.text)
machine.reset()
