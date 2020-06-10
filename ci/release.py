#!/usr/bin/env python3

from argparse import ArgumentParser, Namespace
from datetime import datetime
from os import chdir, getcwd, environ
from hashlib import sha256
from os.path import abspath, dirname, isdir, join
from subprocess import run
from typing import Any, Callable, Dict, List

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from toml import load as load_toml
from yaml import safe_load


artifacts_dir = "artifacts"
packages_dir = "packages"


def cwd() -> None:
  root = dirname(dirname(abspath(__file__)))
  chdir(root)


def run(args: List[str], cwd=getcwd()) -> None:
  ret = run(args, cwd=cwd.encode())
  if ret.returncode != 0:
    exit(ret.returncode)


def load_yaml(src: str) -> Any:
  with open(src) as fd:
    return safe_load(fd)


def load_values() -> Dict[str, str]:
  cargo = load_toml("Cargo.toml")
  vals = load_yaml(join("ci", "vars.yml"))
  values = {"project_repo": "https://github.com/ms-jpq/sad",
            "version": cargo["package"]["version"],
            "desc": vals["desc"],
            "long_desc": vals["long_desc"]}
  return values


def build_j2(src: str, filters: Dict[str, Callable] = {}) -> Environment:
  j2 = Environment(
      enable_async=True,
      trim_blocks=True,
      lstrip_blocks=True,
      undefined=StrictUndefined,
      loader=FileSystemLoader(src))
  j2.filters = {**j2.filters, **filters}
  return j2


def git_clone(name: str) -> None:
  if isdir(name):
    return
  token = environ["CI_TOKEN"]
  email = "ci@ci.ci"
  username = "ci-bot"
  uri = f"https://ms-jpq:{token}@github.com/ms-jpq/homebrew-sad.git"
  run(["git", "clone", uri, name])
  run(["git", "config", "user.email", email], cwd=name)
  run(["git", "config", "user.name", username], cwd=name)


def git_commit(repo: str) -> None:
  time = datetime.now().strftime("%Y-%m-%d %H:%M")
  msg = f"CI - {time}"
  run(["git", "add", "-A"], cwd=repo)
  run(["git", "commit", "-m", msg], cwd=repo)
  run(["git", "push", "--force"], cwd=repo)


def write(filename: str, text: str) -> None:
  with open(filename, "w") as fd:
    fd.write(text)


def sha256(resource: str) -> str:
  with open(resource, "rb") as fd:
    binary = fd.read()
    sha = sha256(binary).hexdigest()
    return sha


def homebrew_release(j2: Environment, values: Dict[str, str], artifact: str, uri: str) -> None:
  sha = sha256(artifact)
  vals = {**values, "sha256": sha, "release_uri": uri}
  render = j2.get_template("homebrew.rb.j2").render(**vals)
  dest = join(packages_dir, "sad.rb")
  write(dest, render)
  git_commit(packages_dir)


def snap_release(j2: Environment, values: Dict[str, str]) -> None:
  vals = {**values}
  render = j2.get_template("snapcraft.yml.j2").render(**vals)
  dest = join(packages_dir, "snapcraft.yaml")
  write(dest, render)
  git_commit(packages_dir)


def parse_args() -> Namespace:
  parser = ArgumentParser()
  parser.add_argument("--brew-artifact")
  parser.add_argument("--brew-uri")
  parser.add_argument("--snapcraft", action="store_true")
  return parser.parse_args()


def main() -> None:
  cwd()
  args = parse_args()
  git_clone(packages_dir)
  j2 = build_j2(join("ci", "templates"))
  values = load_values()
  if args.brew_artifact and args.brew_uri:
    homebrew_release(
        j2=j2,
        values=values,
        artifact=join(artifacts_dir, args.brew_artifact),
        uri=args.brew_uri)
  elif args.snapcraft:
    snap_release(
        j2=j2,
        values=values)
  else:
    exit(1)


main()

