"""
Opal - On-Demand Engine & Model Manager
Plain English: Big tools (AI background removal, AI upscaling, OCR, media encoding) live here.
The first time you use one, Opal quietly downloads just that piece and caches it forever
so the app can keep working offline afterwards. Your files are never sent anywhere: only the
public model files are fetched, from an allowlisted host, over pinned connections.
"""

import os
import sys
import re
import hashlib
import shutil
import socket
import ssl
import ipaddress
import subprocess
import threading
import http.client
from pathlib import Path
from typing import Optional, Callable, Dict, List, Tuple
from urllib.parse import urlsplit

IS_WINDOWS = sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# Model registry: name -> (display name, approx size MB, source url)
# ---------------------------------------------------------------------------

# All cutout models are public ONNX releases; downloads are host-allowlisted.
CUTOUT_BASE_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/{model}.onnx"

CUTOUT_MODELS = {
    "u2net": ("U2-Net (Sharp, all-round)", 176),
    "u2netp": ("U2-Net Lite (Fastest)", 5),
    "isnet-general-use": ("IS-Net (Professional edges)", 175),
    "u2net_human_seg": ("Human Segmenter (Portraits)", 174),
    "isnet-anime": ("Anime & Illustrations", 174),
    "silueta": ("Silueta (Light & simple)", 43),
    "u2net_cloth_seg": ("Cloth Segmenter (Fashion)", 181),
}

ESRGAN_MODELS = {
    "realesrgan-x4plus": ("Real-ESRGAN x4+ (Best quality)", 68,
        "https://github.com/TechFlipsi/FlipsiColor-Models/releases/download/v0.2/RealESRGAN.onnx",
        "0419b536f5bdadaf984b0a3777307dd83e2487e7e13d65a68147b8443f021675"),
    "realesrgan-x2plus": ("Real-ESRGAN x2+ (Lightning)", 68,
        "https://github.com/TechFlipsi/FlipsiColor-Models/releases/download/v0.2/RealESRGAN.onnx",
        "0419b536f5bdadaf984b0a3777307dd83e2487e7e13d65a68147b8443f021675"),
}

# Hosts that may receive a request. Anything else is refused before a socket opens.
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "raw.githubusercontent.com",
}

MAX_REDIRECTS = 5
DOWNLOAD_TIMEOUT = 120


def _app_model_dir() -> Path:
    from opal_studio.platform_compat import user_data_dir
    base = user_data_dir() / "models"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _legacy_model_dir() -> Optional[Path]:
    """Where models lived before the Opal rebrand. Kept so upgrading
    installs do not have to download a multi-megabyte model again."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home())) / "Tangerine" / "engines"
    else:
        return None
    return base if base.is_dir() else None


def _bundled_model_dir() -> Optional[Path]:
    """Models that travel inside the app itself (the full build ships one)."""
    candidates = []
    exe_dir = Path(sys.executable).parent
    candidates.append(exe_dir / "models")
    candidates.append(exe_dir / "_internal" / "models")
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "assets" / "models")
    candidates.append(here / "models")
    for base in candidates:
        if base.is_dir():
            return base
    return None


def _resolve_model_file(name: str) -> Path:
    """Finds a cached model, migrating it out of the legacy folder if needed."""
    target = _app_model_dir() / name
    if target.exists():
        return target
    bundled = _bundled_model_dir()
    if bundled is not None:
        shipped = bundled / name
        if shipped.exists():
            # Copy, never move: the app folder may be read-only.
            try:
                shutil.copy2(shipped, target)
                return target
            except OSError:
                return shipped
    legacy = _legacy_model_dir()
    if legacy is not None:
        old = legacy / name
        if old.exists():
            try:
                old.replace(target)
                return target
            except OSError:
                return old
    return target


def format_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


def human_size(num_bytes: int) -> str:
    if num_bytes >= 1024 ** 3:
        return f"{num_bytes / 1024 ** 3:.1f} GB"
    return f"{num_bytes / 1024 ** 2:.0f} MB"


class UnsafeRequestError(Exception):
    """Raised when a download target fails the allowlist or network-safety checks."""


class EngineStatus:
    """Snapshot of which engines are currently available on this machine."""

    def __init__(self):
        self.ffmpeg: Optional[str] = None
        self.ffprobe: Optional[str] = None
        self.cutout_bundled: bool = False
        self.rapidocr_ready: bool = False
        self.esrgan_ready: Dict[str, bool] = {}

    def describe(self) -> str:
        parts = []
        parts.append("Media: ready" if self.ffmpeg else "Media: missing")
        parts.append("AI cutout: bundled" if self.cutout_bundled else "AI cutout: missing")
        parts.append("OCR: ready" if self.rapidocr_ready else "OCR: loads on first use")
        if any(self.esrgan_ready.values()):
            parts.append("AI upscale: cached")
        return " | ".join(parts)


class CutoutSession:
    """
    Self-contained ONNX session for AI matting models (u2net family & IS-Net family).
    Downloads the public model once through the allowlisted downloader, then runs
    fully offline with onnxruntime. No rembg/pymatting/cupy dependency needed.
    """

    def __init__(self, model_id: str):
        import onnxruntime
        import numpy as np
        self.model_id = model_id
        path = EngineManager.ensure_cutout_model(model_id)
        # If the requested model was unavailable we fell back to one that is
        # already here; report the model that actually ran.
        self.model_id = path.stem or model_id
        so = onnxruntime.SessionOptions()
        so.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        # The cut-out model runs in the same process as the OCR models. With
        # the memory arena on, this session hoards a large block of RAM and
        # the OCR session then fails to allocate and reports an inference
        # error. The arena buys nothing here, so it is turned off.
        so.enable_cpu_mem_arena = False
        # One thread per session also stops the two runtimes fighting over
        # cores on a busy counter PC.
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        try:
            self.session = onnxruntime.InferenceSession(
                str(path), sess_options=so,
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            # A file that cannot be loaded is not a model. Throw it away so
            # the next attempt downloads a clean copy instead of failing
            # for ever with the same message.
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(
                f"The AI model at {path.name} is damaged and has been removed. "
                "Use the tool once more to fetch a clean copy."
            ) from exc
        shape = self.session.get_inputs()[0].shape  # e.g. [1, 3, 320, 320]
        self.input_name = self.session.get_inputs()[0].name
        dim = shape[2] if len(shape) >= 3 and isinstance(shape[2], int) else 320
        self.input_size = int(dim)

    def predict(self, pil_img):
        """Returns an 'L' mask (alpha channel) resized to the original image size."""
        import numpy as np
        from PIL import Image as PILImage
        s = self.input_size
        im = pil_img.convert("RGB").resize((s, s), PILImage.Resampling.LANCZOS)
        arr = np.asarray(im).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        arr = arr.transpose(2, 0, 1)[None]  # NCHW
        out = self.session.run(None, {self.input_name: arr})[0]
        pred = out[:, 0, :, :]
        ma, mi = float(np.max(pred)), float(np.min(pred))
        if ma - mi > 1e-8:
            pred = (pred - mi) / (ma - mi)
        pred = np.squeeze(pred)
        mask = PILImage.fromarray((pred * 255).astype(np.uint8), mode="L")
        return mask.resize(pil_img.size, PILImage.Resampling.LANCZOS)


# ---------------------------------------------------------------------------
# Network safety helpers
# ---------------------------------------------------------------------------

def _validate_download_url(url: str) -> Tuple[str, str, str]:
    """
    Enforces the download safety policy:
      * scheme must be http/https
      * host must be on the allowlist (redirects are re-checked, so none can leave it)
      * every resolved IP must be public (no loopback/private/link-local/reserved)
      * the connection is pinned to a validated IP, so a DNS record that flips after
        the check (rebinding) cannot steer the socket at an internal service
    Returns (scheme, host, pinned_ip). Raises UnsafeRequestError on any violation.
    """
    try:
        parts = urlsplit(url)
    except Exception:
        raise UnsafeRequestError(f"Unparseable URL: {url!r}")

    if parts.scheme not in ("http", "https"):
        raise UnsafeRequestError(f"Scheme not allowed: {parts.scheme!r} (only http/https)")

    host = parts.hostname
    if not host:
        raise UnsafeRequestError("URL has no host")

    if not (host in ALLOWED_DOWNLOAD_HOSTS or any(host.endswith("." + root) for root in ALLOWED_DOWNLOAD_HOSTS)):
        raise UnsafeRequestError(f"Host not allowlisted for downloads: {host!r}")

    try:
        infos = socket.getaddrinfo(
            host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except Exception as e:
        raise UnsafeRequestError(f"DNS resolution failed for {host}: {e}")

    pinned = None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            raise UnsafeRequestError(
                f"Refusing to fetch {host} -> {ip}: loopback/private/reserved address")
        if pinned is None:
            pinned = str(ip)
    if pinned is None:
        raise UnsafeRequestError(f"No usable IP for {host}")
    return parts.scheme, host, pinned


def _pinned_request(url: str, redirects_left: int = MAX_REDIRECTS):
    """
    Opens a GET request to url with the connection pinned to a pre-validated IP.
    Follows redirects manually (max MAX_REDIRECTS), re-validating each target.
    """
    scheme, host, ip = _validate_download_url(url)
    port = 443 if scheme == "https" else 80
    plain_sock = socket.create_connection((ip, port), timeout=DOWNLOAD_TIMEOUT)
    if scheme == "https":
        ctx = ssl.create_default_context()
        conn_sock = ctx.wrap_socket(plain_sock, server_hostname=host)
    else:
        conn_sock = plain_sock

    conn = http.client.HTTPSConnection(host, port=port, timeout=DOWNLOAD_TIMEOUT)
    conn.sock = conn_sock
    target = urlsplit(url)
    path = target.path or "/"
    if target.query:
        path += "?" + target.query
    conn.putrequest("GET", path, skip_accept_encoding=True)
    conn.putheader("Host", host)
    conn.putheader("User-Agent", "Opal/1.0")
    conn.putheader("Connection", "close")
    conn.endheaders()
    resp = conn.getresponse()

    if resp.status in (301, 302, 303, 307, 308):
        location = resp.getheader("Location")
        resp.read()
        conn.close()
        if not location:
            raise UnsafeRequestError("Redirect without Location header")
        if redirects_left <= 0:
            raise UnsafeRequestError("Too many redirects")
        if not location.startswith(("http://", "https://")):
            base = f"{scheme}://{host}"
            location = base + location if location.startswith("/") else f"{base}/{location}"
        return _pinned_request(location, redirects_left - 1)

    return resp, conn.close


def _safe_model_path(raw_dest: str) -> Path:
    """
    Confines model downloads to the Opal engines directory.
    Any '..' component is rejected; the result is rebuilt inside the base
    directory using only the final name, so traversal is impossible.
    """
    parts = Path(raw_dest).parts
    if ".." in parts or len(parts) > 1:
        raise UnsafeRequestError(f"Refusing multi-segment or traversal path: {raw_dest!r}")
    name = parts[0] if parts else ""
    if not name:
        raise UnsafeRequestError(f"Refusing suspicious download path: {raw_dest!r}")
    base = _app_model_dir().resolve()
    return base / name


def _looks_like_model(path: Path) -> bool:
    """Is this file plausibly a model, or is it an error page?

    A download that lands on a 404 or a login page still has a length, so the
    size check alone is not enough. Real ONNX files are protobuf, which never
    starts with an angle bracket, a brace or a bracket.
    """
    try:
        if path.stat().st_size < 64 * 1024:
            return False
        with open(path, "rb") as f:
            head = f.read(64)
    except OSError:
        return False
    if not head:
        return False
    if head[:1] in (b"<", b"{", b"[", b"b", b"\xef\xbb\xbf<"):
        return False
    return True


def _download_with_progress(url: str, dest: str, progress: Optional[Callable[[int, int], None]] = None,
                            expected_sha256: Optional[str] = None) -> None:
    """Downloads url -> dest with a progress callback(downloaded, total). Fully allowlisted.

    When the model has a known fingerprint it is checked before it is kept, so
    a tampered or substituted file never reaches the cache.
    """
    dest_path = _safe_model_path(str(dest))
    base = _app_model_dir().resolve()
    tmp_path = safe_path(base, dest_path.name + ".part")

    resp, close = _pinned_request(url)
    try:
        status = getattr(resp, "status", None) or resp.getcode()
        if status != 200:
            raise UnsafeRequestError(
                f"Model download failed: the server answered {status}, not the model.")
        total = int(resp.getheader("Content-Length") or 0)
        downloaded = 0
        with tmp_path.open("wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress:
                    progress(downloaded, total)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        close()

    if total and downloaded != total:
        tmp_path.unlink(missing_ok=True)
        raise UnsafeRequestError(f"Incomplete download ({downloaded} of {total} bytes)")
    if not _looks_like_model(tmp_path):
        tmp_path.unlink(missing_ok=True)
        raise UnsafeRequestError(
            "The download was not a model file (it looks like an error page). "
            "Nothing was cached; try again.")
    if expected_sha256:
        digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest().lower()
        if digest != expected_sha256.lower():
            tmp_path.unlink(missing_ok=True)
            raise UnsafeRequestError(
                "The downloaded model does not match the expected fingerprint, "
                "so it was discarded and nothing was cached.")
    tmp_path.replace(dest_path)


def _available_providers(onnxruntime) -> List[str]:
    """The execution providers to use, in order.

    We ship the CPU build of onnxruntime, so asking for the GPU provider
    would only produce a warning about missing CUDA. When a GPU really is
    there, it is used.
    """
    try:
        available = set(onnxruntime.get_available_providers())
    except Exception:
        available = set()
    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class EngineManager:
    """
    Singleton-ish helper that resolves optional heavy dependencies lazily.
    All network access happens exactly once per model and is fully cached.
    """

    _rembg_sessions: Dict[str, object] = {}
    _rembg_lock = threading.Lock()
    _rapidocr_engine = None
    _esrgan_sessions: Dict[str, object] = {}
    _esrgan_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Media encoding (FFmpeg)
    # ------------------------------------------------------------------

    @classmethod
    def ffmpeg_bin(cls) -> Optional[str]:
        exe_dir = Path(sys.executable).parent
        for candidate in (exe_dir / "ffmpeg.exe", exe_dir / "_internal" / "ffmpeg.exe"):
            if candidate.exists():
                return str(candidate)
        dist_cand = Path(__file__).resolve().parent.parent / "dist" / "Opal" / "ffmpeg.exe"
        if dist_cand.exists():
            return str(dist_cand)
        # An engine pack installed on demand lives in the user data folder.
        try:
            from opal_studio.engine_packs import engines_dir
            for name in ("ffmpeg.exe", "ffmpeg"):
                candidate = engines_dir() / name
                if candidate.exists():
                    return str(candidate)
        except Exception:
            pass
        backup = Path(__file__).resolve().parent.parent / "ffmpeg_backup" / "ffmpeg.exe"
        if backup.exists():
            return str(backup)
        found = shutil.which("ffmpeg")
        if found:
            return found
        try:
            from static_ffmpeg import get_ffmpeg_path
            p = get_ffmpeg_path()
            if p:
                return str(p)
        except Exception:
            pass
        return None

    @classmethod
    def ffprobe_bin(cls) -> Optional[str]:
        for base in (Path(sys.executable).parent,
                     Path(__file__).resolve().parent.parent / "dist" / "Opal",
                     Path(__file__).resolve().parent.parent / "ffmpeg_backup"):
            cand = base / "ffprobe.exe"
            if cand.exists():
                return str(cand)
        return shutil.which("ffprobe")

    @classmethod
    def ffmpeg_encoders(cls) -> List[str]:
        """Returns the list of codecs this FFmpeg build knows how to write."""
        ff = cls.ffmpeg_bin()
        if not ff:
            return []
        try:
            p = subprocess.run(
                [ff, "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=15,
            )
            out = []
            for line in p.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] in ("V", "A"):
                    out.append(parts[1])
            return out
        except Exception:
            return []

    @classmethod
    def media_duration(cls, src: Path) -> float:
        """The length of a media file, in seconds.

        ffprobe is asked first. When it is not there (the core build does not
        ship it) the answer is read out of ffmpeg's own report instead, so the
        number is still right.
        """
        ffp = cls.ffprobe_bin()
        if ffp:
            try:
                p = subprocess.run(
                    [ffp, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    timeout=15,
                )
                return float(p.stdout.strip())
            except Exception:
                pass
        return cls._duration_from_ffmpeg(src)

    @classmethod
    def _duration_from_ffmpeg(cls, src: Path) -> float:
        """Reads the duration out of what ffmpeg prints about the file."""
        ffmpeg = cls.ffmpeg_bin()
        if not ffmpeg:
            return 0.0
        try:
            p = subprocess.run(
                [ffmpeg, "-i", str(src)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=15,
            )
            report = (p.stderr or "") + (p.stdout or "")
        except Exception:
            return 0.0
        match = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)", report)
        if not match:
            return 0.0
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    # ------------------------------------------------------------------
    # AI background removal (native ONNX pipeline, no fragile dependencies)
    # ------------------------------------------------------------------

    @classmethod
    def cutout_model_path(cls, model: str) -> Path:
        return _resolve_model_file(f"{model}.onnx")

    @classmethod
    def cutout_cached(cls, model: str) -> bool:
        return cls.cutout_model_path(model).exists()

    @classmethod
    def local_cutout_model(cls) -> Optional[Path]:
        """Any cut-out model already on this machine, so a missing download is
        never a dead end. U2-Net Lite is preferred: it is small and quick."""
        for name in ("u2netp", "u2net", "silueta"):
            path = _resolve_model_file(f"{name}.onnx")
            if path.exists():
                return path
        return None

    @classmethod
    def ensure_cutout_model(cls, model: str,
                            progress: Optional[Callable[[int, int], None]] = None) -> Path:
        path = cls.cutout_model_path(model)
        if path.exists():
            return path
        if model not in CUTOUT_MODELS:
            raise ValueError(f"Unknown cutout model: {model}")
        try:
            _download_with_progress(CUTOUT_BASE_URL.format(model=model), f"{model}.onnx", progress)
        except Exception:
            fallback = cls.local_cutout_model()
            if fallback is None:
                raise
            return fallback
        return path

    @classmethod
    def cutout_session(cls, model: str = "u2netp") -> "CutoutSession":
        """Returns a cached ONNX inference session for the requested cutout model."""
        try:
            import onnxruntime  # noqa: F401
        except Exception as e:
            raise RuntimeError(
                "The AI engine is not installed yet. Press \"Remove Background\" in the "
                "Image Lab once - it downloads the engine and works offline after that."
            ) from e
        with cls._rembg_lock:
            sess = cls._rembg_sessions.get(model)
            if sess is not None:
                return sess
            sess = CutoutSession(model)
            cls._rembg_sessions[model] = sess
            return sess

    @classmethod
    def cutout_model_used(cls, model: str) -> str:
        """The model that actually ran, which may be a fallback for the one asked for."""
        sess = cls._rembg_sessions.get(model)
        return getattr(sess, "model_id", model) if sess is not None else model

    @classmethod
    def remove_background(cls, image, model: str = "u2netp",
                          soft_edges: bool = False, crisp: bool = True,
                          progress: Optional[Callable[[str], None]] = None):
        """
        Runs local AI background removal and returns an RGBA PIL image.
        The raw model output is a soft probability map; `crisp` tightens it so
        the cut-out has clean, solid edges instead of a half-transparent haze.
        """
        import numpy as np
        from PIL import Image, ImageFilter
        if progress:
            progress(f"Loading AI cutout model ({model})...")
        session = cls.cutout_session(model)
        if progress:
            progress("Removing background on-device...")
        mask = session.predict(image)
        if crisp and not soft_edges:
            # Push the mid-tones apart: below 40% -> background, above 60% -> subject.
            arr = np.asarray(mask).astype(np.float32)
            arr = np.clip((arr - 40.0) * 2.2, 0, 255).astype(np.uint8)
            mask = Image.fromarray(arr, mode="L")
        if soft_edges:
            mask = mask.filter(ImageFilter.GaussianBlur(1.2))
        rgba = image.convert("RGBA")
        rgba.putalpha(mask)
        return rgba

    @classmethod
    def available_cutout_models(cls) -> List[Tuple[str, str, str]]:
        """Returns (id, display name, cache state) tuples."""
        out = []
        for mid, (label, _size) in CUTOUT_MODELS.items():
            out.append((mid, label, "cached" if cls.cutout_cached(mid) else "cloud"))
        return out

    # ------------------------------------------------------------------
    # AI upscaling (Real-ESRGAN via ONNX Runtime)
    # ------------------------------------------------------------------

    @classmethod
    def esrgan_path(cls, model_id: str) -> Path:
        return _resolve_model_file(f"{model_id}.onnx")

    @classmethod
    def esrgan_cached(cls, model_id: str) -> bool:
        return cls.esrgan_path(model_id).exists()

    @classmethod
    def ensure_esrgan(cls, model_id: str, progress: Optional[Callable[[int, int], None]] = None) -> Path:
        path = cls.esrgan_path(model_id)
        if path.exists():
            return path
        meta = ESRGAN_MODELS.get(model_id)
        if not meta:
            raise ValueError(f"Unknown upscale model: {model_id}")
        _download_with_progress(meta[2], f"{model_id}.onnx", progress, meta[3])
        return path

    @classmethod
    def esrgan_session(cls, model_id: str = "realesrgan-x4plus"):
        import onnxruntime
        with cls._esrgan_lock:
            sess = cls._esrgan_sessions.get(model_id)
            if sess is not None:
                return sess
            path = cls.ensure_esrgan(model_id)
            so = onnxruntime.SessionOptions()
            so.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
            so.enable_cpu_mem_arena = False
            so.intra_op_num_threads = 1
            so.inter_op_num_threads = 1
            try:
                sess = onnxruntime.InferenceSession(
                    str(path), sess_options=so,
                    providers=_available_providers(onnxruntime),
                )
            except Exception as exc:
                # A file that cannot be loaded is not a model. Throw it away so
                # the next attempt downloads a clean copy instead of failing
                # for ever with the same message.
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise RuntimeError(
                    f"The upscaling model at {path.name} is damaged and has been "
                    "removed. Use the tool once more to fetch a clean copy."
                ) from exc
            cls._esrgan_sessions[model_id] = sess
            return sess

    @classmethod
    def upscale(cls, image, model_id: str = "realesrgan-x4plus",
                progress: Optional[Callable[[str], None]] = None):
        """Upscales a PIL RGB image with Real-ESRGAN (model downloads on first use)."""
        import numpy as np
        if progress:
            progress("Initializing AI upscaler (one-time model download)...")
        session = cls.esrgan_session(model_id)
        if progress:
            progress("Upscaling with AI...")
        img = image.convert("RGB")
        factor = 4 if "x4" in model_id else 2
        pad = 64
        w, h = img.size
        pw, ph = (w + pad - 1) // pad * pad, (h + pad - 1) // pad * pad
        arr = np.zeros((ph, pw, 3), dtype=np.uint8)
        arr[:h, :w] = np.asarray(img)
        inp = (arr.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        out = session.run(None, {session.get_inputs()[0].name: inp})[0]
        out = np.clip(out.squeeze().transpose(1, 2, 0) * 255, 0, 255).astype(np.uint8)
        from PIL import Image as PILImage
        return PILImage.fromarray(out[:h * factor, :w * factor])

    # ------------------------------------------------------------------
    # OCR (RapidOCR - bundled offline models)
    # ------------------------------------------------------------------

    @classmethod
    def rapidocr_engine(cls):
        if cls._rapidocr_engine is not None:
            return cls._rapidocr_engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            cls._rapidocr_engine = RapidOCR()
            return cls._rapidocr_engine
        except Exception:
            return None

    @classmethod
    def ocr_available(cls) -> bool:
        return cls.rapidocr_engine() is not None

    # ------------------------------------------------------------------
    # Text-to-speech (Windows SAPI - zero download, fully offline)
    # ------------------------------------------------------------------

    @classmethod
    def tts_speak(cls, text: str, rate: float = 0.0) -> bool:
        if sys.platform != "win32" or not text.strip():
            return False
        try:
            import win32com.client
            import pythoncom
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            if rate:
                voice.Rate = int(max(-10, min(10, rate * 5)))
            voice.Speak(text)
            return True
        except Exception:
            return False

    @classmethod
    def tts_stop(cls) -> None:
        try:
            import win32com.client
            import pythoncom
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            for flag in (1, 2, 3):
                try:
                    voice.Speak("", flag)
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @classmethod
    def status(cls) -> EngineStatus:
        st = EngineStatus()
        st.ffmpeg = cls.ffmpeg_bin()
        st.ffprobe = cls.ffprobe_bin()
        st.cutout_bundled = any(cls.cutout_cached(m) for m in CUTOUT_MODELS)
        st.rapidocr_ready = cls._rapidocr_engine is not None
        for mid in ESRGAN_MODELS:
            st.esrgan_ready[mid] = cls.esrgan_cached(mid)
        return st
