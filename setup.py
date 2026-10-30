"""Metadata lives in pyproject.toml. This file only makes wheels include the compiled web UI."""
import importlib.util
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithFrontend(build_py):
    def run(self):
        path = Path(__file__).resolve().parent / "vbisect" / "frontend_build.py"
        spec = importlib.util.spec_from_file_location("frontend_build", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.ensure_built()
        super().run()


setup(cmdclass={"build_py": BuildWithFrontend})
