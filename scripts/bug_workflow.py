#!/usr/bin/env python3
"""Bug classification and traceable repair workflow."""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from datetime import date
from pathlib import Path
from gate_check import check_signed
from gov_common import find_contract
ROUTES={"implementation_regression":"BUG_FIX","specification_change":"AMENDMENT_OR_NEW_CONTRACT","gate_defect":"MAINTENANCE_M_XXX","environment":"ENVIRONMENT_REMEDIATION","cannot_reproduce":"INVESTIGATE","unknown":"ESCALATE_TO_IO"}
META=re.compile(r"(?:\||>|<|\$\(|`|&&|\|\|)")
def _path(project,bid):
 if not re.fullmatch(r"B-\d{3,}",bid):raise ValueError("bug id must match B-XXX")
 return Path(project).resolve()/"governance/bugs"/f"{bid}.yaml"
def _load(project,bid):
 try:return json.loads(_path(project,bid).read_text())
 except Exception as e:raise ValueError(f"Bug Record unavailable: {bid}") from e
def _save(project,bid,d):p=_path(project,bid);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n");return p
def open_bug(project,bid,task):
 p=_path(project,bid)
 if p.exists():return {"action":"already_exists","path":str(p)}
 d={"version":"1.0","id":bid,"parent_task":task,"created":date.today().isoformat(),"status":"REPORTED","report":{"symptom":"PENDING","expected":"PENDING","actual":"PENDING"},"classification":"unknown","traceability":{"ac_or_preserve":""},"scope_unchanged":None,"permissions_unchanged":None,"approval_boundaries_unchanged":None,"reproduction":{"argv":[],"cwd":".","timeout_seconds":120},"route":"PENDING","red_evidence":None}
 return {"action":"created","path":str(_save(project,bid,d)),"status":"REPORTED"}
def _parent_valid(project,task):
 project=Path(project).resolve();gov=project/"governance"
 try: contract=find_contract(project,task)
 except Exception:return False
 if contract is None:return False
 text=contract.read_text()
 if not check_signed(text)[0]:return False
 legacy_status=bool(re.search(r"\|\s*状态\s*\|\s*(?:COMPLETED|ARCHIVED)\s*\|",text,re.I))
 immutable_closing=(gov/"evidence"/f"EB-{task}.md").exists() and (gov/"telemetry"/"runs"/f"telemetry-{task}.json").exists()
 graph=gov/"Intent_Graph.md";immutable_closing=immutable_closing and graph.exists() and task in graph.read_text()
 return legacy_status or immutable_closing
def classify_bug(project,bid):
 d=_load(project,bid);kind=d.get("classification","unknown");route=ROUTES.get(kind,"ESCALATE_TO_IO");reasons=[]
 if kind=="implementation_regression":
  if not _parent_valid(project,d["parent_task"]):reasons.append("completed signed parent contract missing")
  if not (d.get("traceability") or {}).get("ac_or_preserve"):reasons.append("AC/Preserve traceability missing")
  for k in ("scope_unchanged","permissions_unchanged","approval_boundaries_unchanged"):
   if d.get(k) is not True:reasons.append(k)
  if reasons:route="AMENDMENT_OR_NEW_CONTRACT"
 d["route"]=route;d["status"]="CLASSIFIED" if route=="BUG_FIX" else {"MAINTENANCE_M_XXX":"ROUTED_TO_MAINTENANCE","AMENDMENT_OR_NEW_CONTRACT":"AMENDMENT_REQUIRED","ENVIRONMENT_REMEDIATION":"INVESTIGATING_ENVIRONMENT","INVESTIGATE":"CANNOT_REPRODUCE"}.get(route,"ESCALATED");_save(project,bid,d)
 return {"id":bid,"route":route,"state":d["status"],"reasons":reasons}
def reproduce_bug(project,bid):
 d=_load(project,bid)
 if d.get("route")!="BUG_FIX":return {"passed":False,"state":"BLOCKED","error":"classification does not permit BUG_FIX"}
 r=d.get("reproduction") or {};argv=r.get("argv");timeout=r.get("timeout_seconds",120)
 if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x and not META.search(x) for x in argv):return {"passed":False,"state":"BLOCKED","error":"unsafe or empty argv"}
 if not isinstance(timeout,int) or not 1<=timeout<=300:return {"passed":False,"state":"BLOCKED","error":"invalid timeout"}
 cwd=(Path(project).resolve()/r.get("cwd",".")).resolve()
 try:cwd.relative_to(Path(project).resolve())
 except ValueError:return {"passed":False,"state":"BLOCKED","error":"cwd escapes project"}
 try:out=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=timeout,shell=False)
 except (OSError,subprocess.TimeoutExpired) as e:return {"passed":False,"state":"BLOCKED","error":type(e).__name__}
 if out.returncode<=0:return {"passed":False,"state":"BLOCKED","error":"reproduction did not produce real RED"}
 d["status"]="RED";d["red_evidence"]={"returncode":out.returncode,"stdout":out.stdout[-2000:],"stderr":out.stderr[-2000:]};_save(project,bid,d);return {"passed":True,"state":"RED"}
def bug_status(project,bid):
 d=_load(project,bid);state=d.get("status","REPORTED");actions={"REPORTED":"bug classify","CLASSIFIED":"bug reproduce","RED":"fix via change workflow","VERIFIED":"bug close"};return {"state":state,"route":d.get("route"),"next_action":actions.get(state,"follow route")}
def _delegate(project,task,stage):
 scripts=Path(__file__).resolve().parent
 cmd=[sys.executable,str(scripts/("change_workflow.py" if stage=="verify" else "gate_check.py"))]
 cmd += (["verify","--task",task,"--project-dir",str(project)] if stage=="verify" else ["--gate","bug","--task",task,"--project-dir",str(project)])
 r=subprocess.run(cmd,capture_output=True,text=True);return {"passed":r.returncode==0,"returncode":r.returncode,"output":r.stdout+r.stderr}
def run_bug_stage(project,bid,stage):
 d=_load(project,bid);state=d.get("status","REPORTED")
 required="RED" if stage=="verify" else "VERIFIED"
 if state!=required:return {"state":"BLOCKED","next_action":f"bug {stage}","evidence":f"bug {stage} requires {required}, current state is {state}"}
 if stage=="verify" and not d.get("red_evidence"):return {"state":"BLOCKED","next_action":"bug reproduce","evidence":"real RED evidence missing"}
 result=_delegate(project,d["parent_task"],stage)
 if not result["passed"]:return {"state":"BLOCKED","next_action":f"bug {stage}","evidence":result["output"]}
 d["status"]="VERIFIED" if stage=="verify" else "CLOSED";_save(project,bid,d);return {"state":d["status"],"next_action":"bug close" if stage=="verify" else "none","evidence":result["output"]}
def record_bug_telemetry(project,bid,test_total,test_passed):
 d=_load(project,bid)
 if d.get("status")!="VERIFIED":return {"passed":False,"state":"BLOCKED","error":"bug telemetry requires VERIFIED state"}
 if not isinstance(test_total,int) or not isinstance(test_passed,int) or test_total<1 or test_passed<0 or test_passed>test_total:return {"passed":False,"state":"BLOCKED","error":"invalid test counts"}
 p=Path(project).resolve()/"governance/telemetry/runs"/f"telemetry-{bid}.json";p.parent.mkdir(parents=True,exist_ok=True)
 payload={"version":"1.0","scope":"bug_correction","bug_id":bid,"parent_task":d["parent_task"],"created":date.today().isoformat(),"tests":{"total":test_total,"passed":test_passed},"value":{"first_pass_rate":{"value":0,"reason":"post-release bug correction"}}}
 p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n");return {"passed":True,"state":"RECORDED","path":str(p)}
def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest="cmd",required=True)
 for n in ("open","classify","reproduce","status","verify","telemetry","close"):
  q=s.add_parser(n);q.add_argument("--id",required=True);q.add_argument("--project-dir",default=".");
  if n=="open":q.add_argument("--task",required=True)
  if n=="telemetry":q.add_argument("--test-total",required=True,type=int);q.add_argument("--test-passed",required=True,type=int)
 a=p.parse_args();
 try:
  if a.cmd=="open":r=open_bug(a.project_dir,a.id,a.task)
  elif a.cmd=="classify":r=classify_bug(a.project_dir,a.id)
  elif a.cmd=="reproduce":r=reproduce_bug(a.project_dir,a.id)
  elif a.cmd=="status":r=bug_status(a.project_dir,a.id)
  elif a.cmd=="telemetry":r=record_bug_telemetry(a.project_dir,a.id,a.test_total,a.test_passed)
  else:r=run_bug_stage(a.project_dir,a.id,a.cmd)
 except ValueError as e:print(json.dumps({"error":str(e)}),file=sys.stderr);sys.exit(2)
 print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(1 if r.get("state")=="BLOCKED" or r.get("passed") is False else 0)
if __name__=="__main__":main()
