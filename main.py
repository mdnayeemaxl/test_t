from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Optional
import requests
import paramiko
import time
import json
import os

load_dotenv()
app = FastAPI()

#>>>>>>>>>>>>>>>> CloudeFlare Api Settings <<<<<<<<<<<<<<<<<<<
auth_key = os.getenv('CLDF_AUTH_KEY')
auth_email = os.getenv('CLDF_AUTH_MAIL')
zone_id = os.getenv('CLDF_ZONE_ID')
cloudeurl = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
headers = {"X-Auth-Email": auth_email, "X-Auth-Key": auth_key, "Content-Type": "application/json"}

#>>>>>>>>>>>>>>>> Middleware <<<<<<<<<<<<<<<<<<<
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
    expose_headers=["Content-Disposition"],
)
#>>>>>>>>>>>>>>>> Received Data Model <<<<<<<<<<<<<<<<<<<
class Data(BaseModel):
  id: str
  city: str
  server_ip: str
  name: str
  root: Optional[str] = None 
  server_name: str
  username: Optional[str] = None 
  password: Optional[str] = None 
  country_code: str
  is_installed : str
@app.get("/")
def root():
    return {"message": "Welcome to MicroDeft"}

@app.post("/postserver")
def post_server(data: Data):
  print(auth_key)
  data = data.json()
  loadedData= json.loads(data)
  if(loadedData['password'] and loadedData[root]):
    serverName=loadedData['server_name'].split('.')
    print(loadedData)
    user=serverName[0]
    domain=serverName[1]+'.'+serverName[2]

  # >>>>>>>>>>>>>>>> New DNS Record Record Schema <<<<<<<<<<<<<<<<<<<
    new_dns_record = {
        "type": "A",
        "name": loadedData['server_name'],
        "content": loadedData['server_ip'],
        "ttl": 120,
        "proxied": False
    }
  #>>>>>>>>>>>>>> Send Post Request to CloudeFlare <<<<<<<<<<<<<<<<<< 
    response = requests.post(cloudeurl, headers=headers, json=new_dns_record)
    if response.status_code == 200:
        print("DNS record created successfully.")
    else:
        print("Error:", response.status_code)



  #>>>>>>>>>>>>>>>>>>>SSH Command Executor<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    def ssh_commandExecute(host,userName,password,command,sleepTime):
      session = paramiko.SSHClient()
      session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      session.connect(hostname = host,
                      username= userName,
                      password = password)

      DEVICE_ACCESS = session.invoke_shell()
      for com in command:
          DEVICE_ACCESS.send(f'{com}\n')
          time.sleep(sleepTime)
          print(f'Comment is :{com}')
          output = DEVICE_ACCESS.recv(6500)#65 thousand bytes of data can be stored
          print(output.decode(),end ='')
          print('///////////////////////////////////////////////////////////////////////////////////')
      session.close()

  #>>>>>>>>>>>> Login Host Server and add user to free Radious <<<<<<<<<<<<<<<<<<<<<<<<<<<  
    host = os.getenv('HOST')
    userName = os.getenv('HOST_USER')
    password = os.getenv('HOST_PASS')

    firstCommand='echo "client '+user+' {\nipaddr  = '+loadedData['server_ip']+'/32\nsecret  = SOgVtbvzu8myNigy\n}" >> /etc/freeradius/3.0/clients.conf'
    command=[firstCommand,'systemctl restart freeradius']
    ssh_commandExecute(host,userName,password,command,5)

  #>>>>>>>>>>>>>>>>>>>>>>>>> Make ready user Info For User Login Purpose <<<<<<<<<<<<<<<<<<<<<<<<<<<<
    userDomain = loadedData['server_name']
    userIp = loadedData['server_ip']
    userPass= loadedData['password']
    command1= 'hostnamectl set-hostname '+f'"{userDomain}"'
    command2= 'hostname --file /etc/hostname'
    command3= f'echo "{userIp} {userDomain}" >> /etc/hosts'
    userCommands=[command1,command2,command3,'apt update && apt -y dist-upgrade','apt -y install wget',
                  'wget https://apt.puppetlabs.com/puppet6-release-bullseye.deb', 'dpkg -i puppet6-release-bullseye.deb', 'apt update',
                  'apt -y install puppet-agent iptables','echo "[agent]" >> /etc/puppetlabs/puppet/puppet.conf','echo "server=foreman.covermevpn.com" >> /etc/puppetlabs/puppet/puppet.conf','exit']

  #>>>>>>>>>>>> Login VPN Server (Users) <<<<<<<<<<<<<<<<<<<<<<<<<<< 
    ssh_commandExecute(userIp,"root",userPass,userCommands,10)
    commands=['puppet agent -t','puppet agent -t']
    ssh_commandExecute(userIp,"root",userPass,commands,8)
    userDomain=userDomain.lower()
    url = f'https://covermevpn.com/api/updatevpn.php?host={userDomain}'
    response = requests.get(url)
    print(response.content)
    commands=['puppet agent -t', 'puppet agent -t','puppet agent -t','systemctl enable puppet','systemctl start puppet']
    ssh_commandExecute(userIp,"root",userPass,commands,8)
    return JSONResponse(status_code=200, content={"message": "Congratulations Process has successfully Done !!!"})
  else:
    return JSONResponse(status_code=404, content={"message": "Please Recheck Your given Information"})
