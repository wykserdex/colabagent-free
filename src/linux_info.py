import platform, os, sys
print("Platform:", platform.platform())
print("Python version:", sys.version)
print("Environment variables:")
for k,v in os.environ.items():
    print(f"{k}={v}")