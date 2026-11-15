import os
import sys
import ast
import io
import time
import math
import random
import json
import re
import collections
import itertools
import functools
import shutil
import sqlite3
import traceback
from typing import Dict, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_stats.db")

FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "pty", "ctypes",
    "pathlib", "posix", "nt", "_thread", "threading", "multiprocessing",
    "importlib", "builtins", "code", "pdb", "signal"
}

FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "breakpoint", "exit", "quit"
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            status TEXT,
            exec_time REAL,
            code_len INTEGER,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def audit_ast(code_str: str) -> Tuple[bool, Optional[str]]:
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    for node in ast.walk(tree):
        # Disallow imports of forbidden modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name.split(".")[0]
                if mod_name in FORBIDDEN_MODULES:
                    return False, f"Forbidden import: '{mod_name}'"
        elif isinstance(node, ast.ImportFrom):
            mod_name = (node.module or "").split(".")[0]
            if mod_name in FORBIDDEN_MODULES:
                return False, f"Forbidden from-import: '{mod_name}'"
        
        # Disallow calls to forbidden functions
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_NAMES:
                    return False, f"Forbidden function call: '{node.func.id}()'"
        
        # Disallow access to private and dunder attributes (collections._sys, random._inst ...)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return False, f"Forbidden private attribute: '{node.attr}'"

    return True, None

def execute_sandboxed(code_str: str, timeout_sec: float = 5.0, user_id: int = 0) -> Dict:
    import subprocess
    import tempfile

    start_t = time.time()
    
    # 1. AST Audit
    is_safe, violation = audit_ast(code_str)
    if not is_safe:
        elapsed = time.time() - start_t
        _log_run(user_id, "AST_BLOCKED", elapsed, len(code_str))
        return {
            "success": False,
            "status": "AST_BLOCKED",
            "violation": violation,
            "exec_time": elapsed,
            "stdout": "",
            "error": violation
        }

    # 2. Build isolated subprocess execution environment
    runner_script = """
import sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
except Exception:
    pass

safe_builtins = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "bytearray": bytearray, "bytes": bytes, "chr": chr, "complex": complex,
    "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min, "next": next, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set, "slice": slice,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
    "zip": zip, "True": True, "False": False, "None": None
}
import math, random, time, json, re, collections, itertools, functools, statistics, datetime, string, decimal, fractions
_ALLOWED_IMPORTS = {"math", "random", "time", "json", "re", "collections", "itertools", "functools",
                    "statistics", "datetime", "string", "decimal", "fractions"}
_real_import = __import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    # import разрешён только для модулей из белого списка (остальное режет и проверка AST)
    if level != 0 or name.split(".")[0] not in _ALLOWED_IMPORTS:
        raise ImportError("Module not allowed in sandbox: " + str(name))
    return _real_import(name, globals, locals, fromlist, level)

safe_builtins["__import__"] = _safe_import
safe_builtins["Exception"] = Exception
safe_builtins["ValueError"] = ValueError
safe_builtins["ZeroDivisionError"] = ZeroDivisionError
env_globals = {
    "__builtins__": safe_builtins,
    "math": math, "random": random, "time": time, "json": json,
    "re": re, "collections": collections, "itertools": itertools, "functools": functools
}
with open(sys.argv[1], "r", encoding="utf-8") as f:
    user_code = f.read()

compiled = compile(user_code, "<sandbox>", "exec")
exec(compiled, env_globals)  # один словарь: функции видят друг друга, рекурсия работает
"""

    tmp_user = None
    tmp_runner = None
    sandbox_cwd = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f_user:
            f_user.write(code_str)
            tmp_user = f_user.name
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f_run:
            f_run.write(runner_script)
            tmp_runner = f_run.name

        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "LC_ALL": "en_US.UTF-8",
            "LANG": "en_US.UTF-8",
        }
        sandbox_cwd = tempfile.mkdtemp(prefix="pyb_sandbox_")

        proc = subprocess.Popen(
            [sys.executable, "-I", "-u", tmp_runner, tmp_user],
            env=clean_env,
            cwd=sandbox_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout_txt, stderr_txt = proc.communicate(timeout=timeout_sec)
            elapsed = time.time() - start_t
            success = (proc.returncode == 0)
            raw_out = (stdout_txt + ("\n" + stderr_txt if stderr_txt else "")).strip()
            if len(raw_out) > 4000:
                raw_out = raw_out[:4000] + "\n... [Output truncated to 4000 chars]"
            status_tag = "SUCCESS" if success else "RUNTIME_ERROR"
            _log_run(user_id, status_tag, elapsed, len(code_str))
            return {
                "success": success,
                "status": status_tag,
                "ast_status": "PASSED 🛡",
                "exec_time": elapsed,
                "stdout": raw_out or "(no stdout produced)",
                "error": stderr_txt.strip() if not success else None,
                "error_type": f"ExitCode_{proc.returncode}" if not success else None
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            elapsed = time.time() - start_t
            _log_run(user_id, "TIMEOUT", elapsed, len(code_str))
            return {
                "success": False,
                "status": "TIMEOUT",
                "ast_status": "PASSED 🛡",
                "exec_time": elapsed,
                "stdout": "",
                "error": f"Execution timed out after {timeout_sec:.1f}s",
                "error_type": "TimeoutExpired"
            }
    finally:
        if tmp_user and os.path.exists(tmp_user):
            try: os.unlink(tmp_user)
            except Exception: pass
        if tmp_runner and os.path.exists(tmp_runner):
            try: os.unlink(tmp_runner)
            except Exception: pass
        if sandbox_cwd and os.path.exists(sandbox_cwd):
            try: shutil.rmtree(sandbox_cwd, ignore_errors=True)
            except Exception: pass

def _log_run(user_id: int, status: str, elapsed: float, code_len: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO execution_logs (user_id, status, exec_time, code_len, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, status, elapsed, code_len, time.time()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_runner_stats() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM execution_logs")
    total = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM execution_logs WHERE status = 'SUCCESS'")
    success = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM execution_logs WHERE status = 'AST_BLOCKED'")
    blocked = cur.fetchone()[0] or 0
    failed = total - success - blocked
    cur.execute("SELECT AVG(exec_time) FROM execution_logs")
    avg_t = cur.fetchone()[0] or 0.0
    conn.close()
    return {
        "total_runs": total,
        "success_runs": success,
        "failed_runs": failed,
        "blocked_ast": blocked,
        "avg_time": avg_t
    }

if __name__ == "__main__":
    init_db()
    # Test valid code
    r1 = execute_sandboxed("a = [i**2 for i in range(5)]\nprint('Squares:', a)")
    print("Run 1:", r1["status"], "stdout:", r1["stdout"])

    # Test AST block
    r2 = execute_sandboxed("import os\nos.system('ls')")
    print("Run 2:", r2["status"], "violation:", r2["violation"])
    print("Stats:", get_runner_stats())
