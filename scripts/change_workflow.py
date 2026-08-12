#!/usr/bin/env python3
"""State-aware orchestration for safe solo changes in existing repositories."""
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
from task_recon import scan_task
from gate_check import check_signed
from change_envelope import _load as load_envelope
from evidence_workflow import finalize_evidence

def _plan_path(project,task): return Path(project).resolve()/"governance/change"/f"Change_Plan_{task}.yaml"
def build_plan(project_dir,task_id,targets):
    recon=scan_task(project_dir,task_id,targets);tests=[x for x in recon["candidates"] if x["category"]=="test"]
    return {"version":"1.0","task_id":task_id,"status":"DRAFT","recon":recon,"baseline_required":not bool(tests),"baseline_not_required":{"accepted":False,"source":""},"unknown_decision":{"status":"PENDING","source":""},"history":[]}
def apply_plan(project_dir,plan):
    path=_plan_path(project_dir,plan["task_id"])
    if path.exists(): return {"action":"already_exists","path":str(path)}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"action":"created","path":str(path)}
def _load_plan(project,task):
    path=_plan_path(project,task)
    if not path.exists(): return None
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return None
def _contract(project,task):
    gov=Path(project)/"governance/contracts"
    matches=sorted(gov.glob(f"*{task}.*")) if gov.exists() else []
    if not matches:return False
    try:return check_signed(matches[0].read_text(encoding="utf-8"))[0]
    except Exception:return False
def _envelope_authorized(project,task):
    path=Path(project)/"governance/Change_Envelope.yaml"
    if not path.exists():return False
    try:
        d=load_envelope(path);return d.get("task_id")==task and d.get("status")=="AUTHORIZED" and bool((d.get("allowed") or {}).get("paths")) and not d.get("unknown")
    except Exception:return False
def _baseline_captured(project,task):
    path=Path(project)/"governance/characterization"/f"CB-{task}.yaml"
    if not path.exists():return False
    try:return load_envelope(path).get("status")=="CAPTURED"
    except Exception:return False
def _result(state,next_action,command,**extra):
    return {"state":state,"next_action":next_action,"recommended_command":command,**extra}
def workflow_status(project_dir,task_id):
    project=Path(project_dir).resolve();plan=_load_plan(project,task_id)
    if not plan:return _result("UNPLANNED","change plan",f"python scripts/cli.py change plan --task {task_id} --target <file> --project-dir .")
    if not _contract(project,task_id):return _result("WAITING_FOR_CONTRACT","sign contract",f"review and sign governance/contracts/*{task_id}*")
    if plan.get("recon",{}).get("unknown") and (plan.get("unknown_decision") or {}).get("status")!="ACCEPTED":return _result("WAITING_FOR_UNKNOWN","resolve Recon Unknown",f"record accepted Unknown in signed contract and Change Plan {task_id}")
    if not _envelope_authorized(project,task_id):return _result("WAITING_FOR_ENVELOPE","authorize Change Envelope",f"review governance/Change_Envelope.yaml for {task_id}")
    if plan.get("baseline_required") and not _baseline_captured(project,task_id):return _result("WAITING_FOR_BASELINE","capture Preserve baseline",f"python scripts/cli.py characterize capture --task {task_id} --project-dir .")
    if not plan.get("baseline_required") and not plan.get("recon",{}).get("candidates") and not (plan.get("baseline_not_required") or {}).get("accepted"):return _result("WAITING_FOR_BASELINE","justify baseline decision",f"record baseline_not_required evidence for {task_id}")
    return _result("READY_FOR_ORCHESTRATE","change prepare",f"python scripts/cli.py change prepare --task {task_id} --project-dir .")
def _run_gate(project,task,gate):
    script=Path(__file__).resolve().parent/"gate_check.py";r=subprocess.run([sys.executable,str(script),"--gate",gate,"--task",task,"--project-dir",str(project)],capture_output=True,text=True,check=False)
    return {"passed":r.returncode==0,"gate":gate,"output":r.stdout+r.stderr,"returncode":r.returncode}
def run_stage(project_dir,task_id,stage):
    project=Path(project_dir).resolve()
    if stage=="prepare":
        status=workflow_status(project,task_id)
        if status["state"]!="READY_FOR_ORCHESTRATE":return status
    gate={"prepare":"pre","verify":"prove","close":"closing"}[stage];result=_run_gate(project,task_id,gate)
    if not result["passed"]:return _result("BLOCKED",f"change {stage}",f"python scripts/cli.py change {stage} --task {task_id} --project-dir .",evidence=result["output"],failed_gate=gate)
    telemetry=None
    if stage=="verify":
        try:
            telemetry=finalize_evidence(project,task_id)
        except Exception as exc:
            return _result("BLOCKED","evidence finalize",f"python scripts/cli.py evidence finalize --task {task_id} --project-dir .",evidence=str(exc),failed_gate="evidence_finalize",prove=result["output"])
    state={"prepare":"READY_FOR_ORCHESTRATE","verify":"VERIFIED","close":"CLOSED"}[stage]
    next_step={"prepare":"begin TDD Orchestrate","verify":"run closing gate","close":"none"}[stage]
    command={"prepare":"follow signed contract and TDD","verify":f"python scripts/cli.py change close --task {task_id} --project-dir .","close":""}[stage]
    extra={"telemetry":telemetry} if telemetry is not None else {}
    return _result(state,next_step,command,evidence=result["output"],**extra)
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("plan");q.add_argument("--task",required=True);q.add_argument("--target",action="append",required=True);q.add_argument("--project-dir",default=".");q.add_argument("--apply",action="store_true")
    for name in ("status","prepare","verify","close"):
        q=sub.add_parser(name);q.add_argument("--task",required=True);q.add_argument("--project-dir",default=".")
    a=p.parse_args()
    if a.cmd=="plan":
        plan=build_plan(a.project_dir,a.task,a.target);r={"plan":plan,"write":{"action":"dry_run"}}
        if a.apply:r["write"]=apply_plan(a.project_dir,plan)
    elif a.cmd=="status":r=workflow_status(a.project_dir,a.task)
    else:r=run_stage(a.project_dir,a.task,a.cmd)
    print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(1 if r.get("state")=="BLOCKED" else 0)
if __name__=="__main__":main()
