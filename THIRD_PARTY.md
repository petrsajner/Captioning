# Third-party components

Caption Studio's own interface and batch engine are original implementation.
JoyCaption Alpha Two was consulted as a user-facing workflow reference; its source
code and weights are not bundled.

The frozen Windows package includes Python (PSF license), FastAPI (MIT), Starlette
(BSD-3-Clause), Pydantic (MIT), Uvicorn (BSD-3-Clause), HTTPX/HTTPCore (BSD-3-Clause),
Pillow (MIT-CMU), pywebview (BSD-3-Clause), Python.NET (MIT), and their dependencies.
The `licenses` folder in the installed application contains the license files and
package metadata collected from the build environment. Microsoft's system
WebView2 component is used when installed; it is not bundled in this package.

Downloaded separately on user request:

- llama.cpp b10821: MIT; https://github.com/ggml-org/llama.cpp/tree/b10821
- CUDA runtime libraries from the official llama.cpp release: NVIDIA license
  terms apply; https://docs.nvidia.com/cuda/eula/index.html
- Qwen3.8-27B GGUF by Unsloth: Apache-2.0 model card;
  https://huggingface.co/unsloth/Qwen3.8-27B-GGUF
  pinned revision: `4ca720788d1e01f1bff70c033e0d0028fd02e502`.

Model downloads and runtime archives are pinned and checked against SHA-256
metadata from the upstream repositories. Upstream license and acceptable-use
terms apply to those components. Cloud services are optional and governed by the
chosen provider's own terms and pricing.
