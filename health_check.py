#!/usr/bin/env python3
"""
Health check script for EverQuest Forum Crafting Bot
Can be used for monitoring, Docker health checks, or automated restarts
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_pid_file():
    """Check if bot is running via PID file"""
    pid_file = Path("eq_bot.pid")
    if not pid_file.exists():
        return False, "PID file not found"
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is actually running
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True, f"Bot running with PID {pid}"
        except OSError:
            return False, f"Process {pid} not found"
    except Exception as e:
        return False, f"Error reading PID file: {e}"

def check_log_file():
    """Check if bot is logging recent activity"""
    log_file = Path("logs/eq_bot.log")
    if not log_file.exists():
        return False, "Log file not found"
    
    try:
        # Check if log has been updated in the last 5 minutes
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        if datetime.now() - mtime > timedelta(minutes=5):
            return False, f"Log file last updated {mtime}"
        
        # Check for recent ERROR entries
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-50:]  # Check last 50 lines
            
            error_count = sum(1 for line in recent_lines if " ERROR " in line)
            if error_count > 10:  # Too many errors
                return False, f"High error count in recent logs: {error_count}"
        
        return True, "Log file looks healthy"
    except Exception as e:
        return False, f"Error checking log file: {e}"

def check_environment():
    """Check if required environment variables are set"""
    required_vars = ['DISCORD_BOT_TOKEN', 'WATCHED_FORUM_ID']
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        return False, f"Missing environment variables: {missing}"
    
    return True, "Environment variables OK"

def check_dependencies():
    """Check if required Python packages are available"""
    required_packages = ['discord', 'aiohttp']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        return False, f"Missing packages: {missing}"
    
    return True, "Dependencies OK"

def run_health_check():
    """Run all health checks and return overall status"""
    checks = [
        ("Environment", check_environment),
        ("Dependencies", check_dependencies),
        ("PID File", check_pid_file),
        ("Log File", check_log_file),
    ]
    
    results = {}
    overall_healthy = True
    
    for name, check_func in checks:
        try:
            healthy, message = check_func()
            results[name] = {"healthy": healthy, "message": message}
            if not healthy:
                overall_healthy = False
        except Exception as e:
            results[name] = {"healthy": False, "message": f"Check failed: {e}"}
            overall_healthy = False
    
    return overall_healthy, results

def main():
    """Main health check entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="EverQuest Bot Health Check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only show overall status")
    parser.add_argument("--check", choices=["env", "deps", "pid", "log"], help="Run specific check only")
    
    args = parser.parse_args()
    
    # Run specific check if requested
    if args.check:
        check_map = {
            "env": ("Environment", check_environment),
            "deps": ("Dependencies", check_dependencies),
            "pid": ("PID File", check_pid_file),
            "log": ("Log File", check_log_file),
        }
        
        name, check_func = check_map[args.check]
        healthy, message = check_func()
        
        if args.json:
            print(json.dumps({"healthy": healthy, "message": message}))
        else:
            status = "✓" if healthy else "✗"
            print(f"{status} {name}: {message}")
        
        sys.exit(0 if healthy else 1)
    
    # Run all checks
    overall_healthy, results = run_health_check()
    
    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "healthy": overall_healthy,
            "checks": results
        }
        print(json.dumps(output, indent=2))
    elif args.quiet:
        print("HEALTHY" if overall_healthy else "UNHEALTHY")
    else:
        print(f"=== EverQuest Bot Health Check ===")
        print(f"Timestamp: {datetime.now()}")
        print(f"Overall Status: {'✓ HEALTHY' if overall_healthy else '✗ UNHEALTHY'}")
        print()
        
        for name, result in results.items():
            status = "✓" if result["healthy"] else "✗"
            print(f"{status} {name}: {result['message']}")
    
    sys.exit(0 if overall_healthy else 1)

if __name__ == "__main__":
    main()