# Installation

## Engine only

Python 3.9 or newer is sufficient for catalog discovery, composition, inspection, and
control-plane tests.

```bash
git clone -b sol-engine https://github.com/NVlabs/Sana.git
cd Sana
python3 -m pip install --upgrade "pip>=24" "setuptools>=69"
python3 -m pip install -e .
sol doctor
```

The build-tool upgrade matters on systems that still ship pip 21: that version can
misread modern `pyproject.toml` metadata and create an `UNKNOWN` package. The engine core
has no mandatory PyTorch dependency. `pip install -e .[runtime]` installs
the optional runtime dependency declared by this repository, but a released model may
still require its backend checkout and model-specific packages.

## Sol-Attn kernels

Install PyTorch for the target CUDA architecture first, then install the optional kernel
package:

```bash
python3 -m pip install -e sol/optimizations/sparse_backends
```

This prevents the kernel package from replacing a PyTorch build already matched to the
machine. Refer to its README for supported GPU architectures and backend fallback.

## Model runtimes

Each released model plugin declares its execution backend. The current LTX-2.3 release
uses an external SGLang checkout; its path is supplied as `SGLANG_RUNTIME_ROOT`. Follow
that checkout's installation instructions, then provide explicit weight paths as shown
in the repository's
[Quickstart](https://github.com/NVlabs/Sana/blob/sol-engine/QUICKSTART.md).

Diffusers dependencies are used for semantic references and model bring-up. A Diffusers
reference being present does not imply that its performance path has been released.
