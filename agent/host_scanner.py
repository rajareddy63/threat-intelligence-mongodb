#!/usr/bin/env python3
"""Read-only host security inventory. No remediation commands are executed."""
import argparse, json, os, platform, socket, subprocess, uuid
from datetime import datetime, timezone
from pathlib import Path
import requests
def run(cmd,timeout=25):
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,shell=False)
  return (p.stdout or p.stderr).strip()
 except Exception as e:return f"unavailable: {e}"
def finding(title,severity,category,evidence,remediation):
 return {"finding_id":str(uuid.uuid4()),"title":title,"severity":severity,"category":category,"evidence":evidence[:1800],"remediation":remediation,"status":"Active"}
def windows_findings():
 out=[]
 ps="Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json -Compress"
 data=run(["powershell","-NoProfile","-NonInteractive","-Command",ps])
 try:
  d=json.loads(data)
  if d.get("AntivirusEnabled") is False or d.get("RealTimeProtectionEnabled") is False:
   out.append(finding("Microsoft Defender protection is disabled","high","endpoint_protection",data,"Review Windows Security and re-enable real-time protection if this is not an intentional managed policy."))
 except:out.append(finding("Defender status could not be verified","low","visibility",data,"Run PowerShell as an authorized user and check Get-MpComputerStatus."))
 fw=run(["powershell","-NoProfile","-NonInteractive","-Command","Get-NetFirewallProfile | Select-Object Name,Enabled | ConvertTo-Json -Compress"])
 try:
  profiles=json.loads(fw); profiles=profiles if isinstance(profiles,list) else [profiles]
  off=[x.get("Name") for x in profiles if x.get("Enabled") is False]
  if off:out.append(finding("Windows Firewall profile disabled","high","firewall",f"Disabled profiles: {off}","Review Windows Defender Firewall policy and enable required profiles; check managed-device policy first."))
 except:out.append(finding("Firewall state could not be parsed","low","visibility",fw,"Inspect Get-NetFirewallProfile output manually."))
 updates=run(["powershell","-NoProfile","-NonInteractive","-Command","(New-Object -ComObject Microsoft.Update.AutoUpdate).Results | Format-List"])
 if "error" in updates.lower() or not updates:
  out.append(finding("Windows Update status not confirmed","medium","patching",updates,"Open Settings > Windows Update, check for updates, and install security updates after reviewing restart requirements."))
 osinfo=run(["powershell","-NoProfile","-NonInteractive","-Command","Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,LastBootUpTime | ConvertTo-Json -Compress"])
 out.append(finding("Windows OS build inventory collected","info","inventory",osinfo,"Compare the OS edition/build with Microsoft's supported lifecycle and security update baseline."))
 hotfix=run(["powershell","-NoProfile","-NonInteractive","-Command","Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 HotFixID,InstalledOn | ConvertTo-Json -Compress"])
 out.append(finding("Windows patch inventory collected","info","inventory",hotfix,"Compare installed KBs with your organization's patch baseline and Microsoft Security Update Guide."))
 pending=run(["powershell","-NoProfile","-NonInteractive","-Command","try { $s=New-Object -ComObject Microsoft.Update.Session; $r=$s.CreateUpdateSearcher().Search(\"IsInstalled=0 and Type='Software'\"); [pscustomobject]@{PendingCount=$r.Updates.Count; Titles=@($r.Updates | Select-Object -First 15 -ExpandProperty Title)} | ConvertTo-Json -Compress } catch { \"Update scan unavailable: $_\" }"],timeout=90)
 try:
  pd=json.loads(pending)
  if int(pd.get("PendingCount",0))>0:out.append(finding("Pending Windows updates detected","medium","patching",pending,"Review the pending update titles in Settings > Windows Update; prioritize security updates and plan a restart window."))
  else:out.append(finding("Pending Windows update query completed","info","patching",pending,"Continue checking vendor security advisories and your organization's patch compliance baseline."))
 except:out.append(finding("Pending Windows updates could not be verified","low","visibility",pending,"Run the scanner with permissions that allow the Windows Update Agent query, or check Settings > Windows Update manually."))
 return out
def linux_findings():
 out=[]
 osrel=run(["sh","-lc","cat /etc/os-release"])
 out.append(finding("Linux distribution inventory","info","inventory",osrel,"Use the distribution's supported security update channel and confirm maintenance status."))
 if Path("/usr/bin/apt").exists():
  up=run(["sh","-lc","apt list --upgradable 2>/dev/null | head -80"])
  if up.count("\n")>1:out.append(finding("Packages have available updates","medium","patching",up,"Review the package list and apply security updates using your distribution's approved maintenance process."))
 if Path("/usr/sbin/ufw").exists():
  fw=run(["ufw","status"])
  if "inactive" in fw.lower():out.append(finding("UFW firewall is inactive","medium","firewall",fw,"Review firewall policy and enable only after allowing required management and application traffic."))
 ssh=run(["sh","-lc","sshd -T 2>/dev/null | grep -E 'permitrootlogin|passwordauthentication'"])
 if ssh and ("permitrootlogin yes" in ssh.lower() or "passwordauthentication yes" in ssh.lower()):
  out.append(finding("SSH permits potentially weak authentication settings","medium","remote_access",ssh,"Review SSH hardening policy; prefer key-based authentication and restrict privileged remote login after testing access."))
 return out
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--api",default=os.getenv("THREAT_API_URL","http://localhost:8000"))
 ap.add_argument("--platform",choices=["Windows","Linux"],default="Windows" if platform.system()=="Windows" else "Linux")
 ap.add_argument("--host",default=socket.gethostname())
 args=ap.parse_args()
 findings=windows_findings() if args.platform=="Windows" else linux_findings()
 payload={"platform":args.platform,"host":args.host,"findings":findings}
 print(json.dumps(payload,indent=2))
 try:
  r=requests.post(args.api.rstrip("/")+"/api/scan-results",json=payload,timeout=20)
  r.raise_for_status();print("\nUploaded scan:",r.json())
 except Exception as e:print("\nCould not upload scan. Start the Docker application and retry:",e)
if __name__=="__main__":main()
