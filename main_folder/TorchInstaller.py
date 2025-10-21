import subprocess
import sys
import re

def query_nvidia_smi():
    """Return (gpu_name, cuda_driver_version) or (None, None) if nvidia-smi fails."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # e.g. "GeForce RTX 3080, 535.54.03"
        name, driver = [s.strip() for s in out.split(",")]
        return name, driver
    except Exception:
        return None, None

def map_driver_to_cuda(driver_version):
    """
    Map NVIDIA driver version to highest supported CUDA runtime.
    This is heuristic; you may need to adjust based on PyTorch wheel availability.
    """
    # extract major.minor from driver version string
    m = re.match(r"(\d+)\.(\d+)", driver_version or "")
    if not m:
        return None
    major, minor = map(int, m.groups())
    # Example thresholds—tweak to match PyTorch support matrix:
    if major >= 535:
        return "cu124"   # CUDA 12.4
    if major >= 530:
        return "cu121"   # CUDA 12.1
    if major >= 515:
        return "cu118"   # CUDA 11.8
    if major >= 510:
        return "cu117"   # CUDA 11.7
    if major >= 470:
        return "cu116"   # CUDA 11.6
    return None          # too old → fallback to CPU

def install_torch(cuda_tag):
    """
    pip-install the matching torch wheel.  If cuda_tag is None → CPU-only.
    """
    pkg = "torch"
    if cuda_tag:
        pkg = f"torch==2.1.0+{cuda_tag}"
        index_url = "https://download.pytorch.org/whl/torch_stable.html"
        cmd = [sys.executable, "-m", "pip", "install", pkg, "--index-url", index_url]
    else:
        # CPU wheel
        cmd = [sys.executable, "-m", "pip", "install", "torch", "--index-url",
               "https://download.pytorch.org/whl/cpu"]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)

if __name__ == "__main__":
    gpu_name, driver_ver = query_nvidia_smi()
    if gpu_name:
        print(f"Detected GPU: {gpu_name}  Driver: {driver_ver}")
    else:
        print("No NVIDIA GPU detected (or nvidia-smi not on PATH).")
    cuda = map_driver_to_cuda(driver_ver)
    if cuda:
        print(f"→ Installing GPU-accelerated torch ({cuda})")
    else:
        print("→ Installing CPU-only torch")
    install_torch(cuda)
    # then import torch and continue with your application…
