import os
import subprocess
import shutil
import argparse
from pathlib import Path

class DecompilerManager:
    def __init__(self, output_base="output/decompiled"):
        self.output_base = Path(output_base)
        self.output_base.mkdir(parents=True, exist_ok=True)

    def decompile_dotnet(self, file_path):
        """Uses ilspycmd to decompile .NET assemblies."""
        out_dir = self.output_base / "dotnet" / Path(file_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[.NET] Decompiling {file_path} to {out_dir}...")
        
        try:
            # Command: ilspycmd -o <out_dir> -p <file_path>
            subprocess.run(["ilspycmd", "-o", str(out_dir), "-p", str(file_path)], check=True)
            return True
        except FileNotFoundError:
            print("[ERROR] 'ilspycmd' not found. Install with: dotnet tool install -g ilspycmd")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] .NET decompilation failed: {e}")
        return False

    def decompile_java(self, file_path):
        """Uses CFR to decompile Java .class or .jar files."""
        out_dir = self.output_base / "java" / Path(file_path).stem
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Java] Decompiling {file_path} to {out_dir}...")
        
        # We expect cfr.jar to be in tools/bin or on path
        cfr_jar = Path("tools/bin/cfr.jar")
        
        try:
            cmd = ["java", "-jar", str(cfr_jar), str(file_path), "--outputdir", str(out_dir)]
            subprocess.run(cmd, check=True)
            return True
        except FileNotFoundError:
            print("[ERROR] 'java' or 'cfr.jar' not found.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Java decompilation failed: {e}")
        return False

    def decompile_python(self, file_path):
        """Uses uncompyle6 to decompile .pyc files."""
        out_file = self.output_base / "python" / (Path(file_path).stem + ".py")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Python] Decompiling {file_path} to {out_file}...")
        
        try:
            with open(out_file, "w") as f:
                subprocess.run(["uncompyle6", str(file_path)], stdout=f, check=True)
            return True
        except FileNotFoundError:
            print("[ERROR] 'uncompyle6' not found. Install with: pip install uncompyle6")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Python decompilation failed: {e}")
        return False

    def route_file(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext in ['.dll', '.exe']:
            return self.decompile_dotnet(file_path)
        elif ext in ['.class', '.jar']:
            return self.decompile_java(file_path)
        elif ext in ['.pyc']:
            return self.decompile_python(file_path)
        else:
            print(f"[SKIP] No decompiler for {ext} files.")
            return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Decompile binary artifacts for static analysis.")
    parser.add_argument("file", help="Path to the binary file (DLL, JAR, PYC, etc.)")
    parser.add_argument("--out", default="output/decompiled", help="Base output directory")
    
    args = parser.parse_args()
    manager = DecompilerManager(args.out)
    manager.route_file(args.file)
