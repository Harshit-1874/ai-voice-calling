#!/usr/bin/env python3
import os
import shutil
import glob
from pathlib import Path

def copy_prisma_engines():
    """Copy Prisma query engine binaries to the correct location for Python"""
    
    # Common paths where Prisma Python stores binaries
    possible_source_paths = [
        "/opt/render/.cache/prisma-python/binaries/**/*prisma-query-engine-debian-openssl-3.0.x*",
        "/opt/render/project/src/**/*prisma-query-engine-debian-openssl-3.0.x*",
        "~/.cache/prisma-python/binaries/**/*prisma-query-engine-debian-openssl-3.0.x*",
        "./.prisma/**/*prisma-query-engine-debian-openssl-3.0.x*"
    ]
    
    # Target locations where Python Prisma looks for binaries
    target_paths = [
        "/opt/render/project/src/backend/",
        "/opt/render/project/src/",
        "./"
    ]
    
    print("🔍 Searching for Prisma query engine binaries...")
    
    # Find the source binary
    source_binary = None
    for pattern in possible_source_paths:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            source_binary = matches[0]
            print(f"✅ Found binary at: {source_binary}")
            break
    
    if not source_binary:
        print("❌ No query engine binary found!")
        return False
    
    # Copy to target locations
    binary_name = "prisma-query-engine-debian-openssl-3.0.x"
    success = False
    
    for target_dir in target_paths:
        try:
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, binary_name)
            shutil.copy2(source_binary, target_path)
            os.chmod(target_path, 0o755)  # Make executable
            print(f"✅ Copied binary to: {target_path}")
            success = True
        except Exception as e:
            print(f"⚠️  Failed to copy to {target_dir}: {e}")
    
    return success

if __name__ == "__main__":
    if copy_prisma_engines():
        print("🎉 Prisma binary copy completed successfully!")
    else:
        print("❌ Failed to copy Prisma binaries")
        exit(1)
