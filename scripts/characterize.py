#!/usr/bin/env python3
"""Safe characterization planning, baseline capture, and verification."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SUGGEST={".py":"python3 -m unittest / pytest",".js":"npm test / node --test",".ts":"npm test / vitest",".tsx":"npm test / vitest",".c":"ctest / make test",".cpp":"ctest / make test",".h":"ctest / make test",".hpp":"ctest / make test",".java":"mvn test / gradle test",".jsp":"mvn test plus servlet integration test",".go":"go test ./...",".rs":"cargo test",".sh":"bats / shell test"}
SENSITIVE=re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s]{6,}")
SHELL_META=re.compile(r"(?:\||>|<|\$\(|`|&&|\|\|)")

def _load(path):
    try: text=Path(path).read_text(encoding="utf-8")
    except OSError as e: raise ValueError(f"baseline not readable: {path}") from e
    try: data=json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            from _bootstrap import ensure_yaml_available
            ensure_yaml_available()
            import yaml
        try: data=yaml.safe_load(text)
        except Exception as e: raise ValueError("baseline is not valid YAML/JSON") from e
    if not isinstance(data,dict): raise ValueError("baseline root must be an object")
    return data

def _hash(value): return hashlib.sha256(value.encode("utf-8")).hexdigest()
def _config_fingerprint(d):
    picked={k:d.get(k) for k in ("task_id","targets","preserve","observations","normalization")}
    return _hash(json.dumps(picked,sort_keys=True,ensure_ascii=False,separators=(",",":")))

def plan_baseline(project_dir,task_id,targets):
    project=Path(project_dir).resolve(); resolved=[]; suggestions=[]
    for raw in targets:
        p=(project/raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try: rel=p.relative_to(project).as_posix()
        except ValueError as e: raise ValueError(f"target escapes project: {raw}") from e
        if not p.is_file(): raise ValueError(f"target must exist and be a file: {raw}")
        resolved.append(rel); suggestions.append({"target":rel,"suggestion":SUGGEST.get(p.suffix.lower(),"project-specific test command required")})
    return {"version":"1.0","task_id":task_id,"status":"DRAFT","targets":resolved,"preserve":[],"test_suggestions":suggestions,"observations":[],"normalization":{"redact_patterns":[],"ignore_line_patterns":[]},"unknown":["IO must confirm Preserve behavior and observation commands"]}

def _validate(project,task,d):
    if d.get("task_id")!=task: raise ValueError("task_id mismatch")
    if d.get("status")!="AUTHORIZED": raise ValueError("baseline must be AUTHORIZED")
    preserve=d.get("preserve")
    if not isinstance(preserve,list) or not preserve: raise ValueError("at least one Preserve behavior is required")
    if any(x.get("source") not in {"IO confirmed","existing test"} for x in preserve if isinstance(x,dict)) or any(not isinstance(x,dict) for x in preserve): raise ValueError("Preserve source must be IO confirmed or existing test")
    if d.get("unknown"): raise ValueError("Unknown must be empty")
    obs=d.get("observations")
    if not isinstance(obs,list) or not obs: raise ValueError("at least one observation is required")
    for o in obs:
        argv=o.get("argv") if isinstance(o,dict) else None
        if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv): raise ValueError("argv must be a non-empty string array")
        if any(SHELL_META.search(x) for x in argv): raise ValueError("shell operators are forbidden")
        timeout=o.get("timeout_seconds",120)
        if not isinstance(timeout,int) or not 1<=timeout<=300: raise ValueError("timeout_seconds must be 1..300")
        cwd=(project/o.get("cwd",".")).resolve()
        try: cwd.relative_to(project)
        except ValueError as e: raise ValueError("observation cwd escapes project") from e

def _normalize(text,rules):
    lines=text.replace("\r\n","\n").splitlines()
    for pattern in rules.get("ignore_line_patterns",[]): lines=[x for x in lines if not re.search(pattern,x)]
    result="\n".join(lines)
    for pattern in rules.get("redact_patterns",[]): result=re.sub(pattern,"[REDACTED]",result)
    return result

def _run(project,o,rules):
    cwd=(project/o.get("cwd",".")).resolve()
    try: r=subprocess.run(o["argv"],cwd=cwd,capture_output=True,text=True,timeout=o.get("timeout_seconds",120),shell=False)
    except (subprocess.TimeoutExpired,OSError) as e: return {"status":"UNVERIFIABLE","error":type(e).__name__}
    combined=(r.stdout or "")+"\n"+(r.stderr or "")
    normalized=_normalize(combined,rules)
    if SENSITIVE.search(normalized): return {"status":"SENSITIVE_OUTPUT","error":"sensitive output detected"}
    return {"status":"OK","exit_code":r.returncode,"summary_sha256":_hash(normalized),"summary_preview":normalized[:240],"line_count":len(normalized.splitlines())}

def _fail(task,status,error): return {"task_id":task,"passed":False,"status":status,"errors":[error],"observations":[]}

def capture_baseline(project_dir,task_id,baseline_path):
    project=Path(project_dir).resolve(); path=Path(baseline_path)
    try: d=_load(path); _validate(project,task_id,d)
    except ValueError as e: return _fail(task_id,"REJECTED",str(e))
    results=[]; rules=d.get("normalization") or {}
    for o in d["observations"]:
        r=_run(project,o,rules); results.append({"id":o.get("id"),**r})
        if r["status"]!="OK": return _fail(task_id,"UNVERIFIABLE" if r["status"]=="UNVERIFIABLE" else "REJECTED",r.get("error",r["status"]))
        if r["exit_code"]!=o.get("expected_exit_code",0): return _fail(task_id,"REJECTED",f"unexpected exit code for {o.get('id')}")
    d["status"]="CAPTURED";d["capture"]={"captured_at":datetime.now(timezone.utc).isoformat(),"config_fingerprint":_config_fingerprint(d),"environment_fingerprint":_hash(platform.platform()+sys.version+str(project)),"observations":results}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"task_id":task_id,"passed":True,"status":"CAPTURED","errors":[],"observations":results}

def verify_baseline(project_dir,task_id,baseline_path):
    project=Path(project_dir).resolve()
    try: d=_load(baseline_path)
    except ValueError as e: return _fail(task_id,"UNVERIFIABLE",str(e))
    if d.get("task_id")!=task_id or d.get("status")!="CAPTURED" or not d.get("capture"): return _fail(task_id,"UNVERIFIABLE","captured baseline required")
    if _config_fingerprint(d)!=d["capture"].get("config_fingerprint"): return _fail(task_id,"UNVERIFIABLE","baseline configuration changed")
    current=[]; changed=[]
    for o,old in zip(d["observations"],d["capture"]["observations"]):
        r=_run(project,o,d.get("normalization") or {});current.append({"id":o.get("id"),**r})
        if r.get("status")!="OK": return _fail(task_id,"UNVERIFIABLE",r.get("error",r["status"]))
        if r.get("exit_code")!=old.get("exit_code") or r.get("summary_sha256")!=old.get("summary_sha256"): changed.append(o.get("id"))
    return {"task_id":task_id,"passed":not changed,"status":"SAME" if not changed else "CHANGED","errors":[],"changed":changed,"observations":current}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
    q=sub.add_parser("plan");q.add_argument("--task",required=True);q.add_argument("--target",action="append",required=True);q.add_argument("--project-dir",default=".");q.add_argument("--output")
    for name in ("capture","verify"):
        q=sub.add_parser(name);q.add_argument("--task",required=True);q.add_argument("--project-dir",default=".");q.add_argument("--baseline")
    a=p.parse_args(); default=Path(a.project_dir)/"governance/characterization"/f"CB-{a.task}.yaml"
    if a.cmd=="plan":
        r=plan_baseline(a.project_dir,a.task,a.target);text=json.dumps(r,ensure_ascii=False,indent=2)+"\n"
        if a.output: Path(a.output).write_text(text,encoding="utf-8");print(a.output)
        else: print(text,end="")
        return
    r=(capture_baseline if a.cmd=="capture" else verify_baseline)(a.project_dir,a.task,a.baseline or default);print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(0 if r["passed"] else 1)
if __name__=="__main__": main()
