from abc import ABC, abstractmethod
import typing
import os
import subprocess
import json
import shutil
import hashlib
import tarfile
from urllib.request import urlopen

MINIBREW_PATH = os.path.dirname(os.path.realpath(__file__))
REPOS_PATH = os.path.join(MINIBREW_PATH, 'repos')
PKGS_PATH = os.path.join(MINIBREW_PATH, 'pkgs')
INSTALL_JSON_PATH = os.path.join(PKGS_PATH, 'install.json')
MSBUILD_SCRIPT_PATH = os.path.join(MINIBREW_PATH, 'scripts', 'msbuild.bat')
_windows = os.name == 'nt'

try:
  with open(INSTALL_JSON_PATH) as f:
    _installJson: typing.Dict[str, str] = json.load(f)
except FileNotFoundError:
  _installJson: typing.Dict[str, str] = {}


def _saveInstallJson():
  os.makedirs(os.path.dirname(INSTALL_JSON_PATH), exist_ok=True)
  with open(INSTALL_JSON_PATH, 'w') as f:
    json.dump(_installJson, f, indent=2)


def run(
    command: typing.List[str],
    *,
    cwd: typing.Optional[str]=None,
    env: typing.Optional[typing.Dict[str, str]]=None) -> None:
  e = os.environ.copy()
  if env:
    e.update(env)
  subprocess.run(command, check=True, cwd=cwd, env=e)


class Source(ABC):

  @abstractmethod
  def get(self, repoPath: str) -> None:
    pass

  @abstractmethod
  def getKey(self) -> str:
    pass


class Git(Source):
  repository: str
  commit: str

  def __init__(self, *, repository: str, commit: str) -> None:
    super().__init__()
    self.repository = repository
    self.commit = commit

  def get(self, repoPath: str) -> None:
    os.makedirs(REPOS_PATH, exist_ok=True)
    if os.path.exists(repoPath):
      shutil.rmtree(repoPath)
    run(['git', 'clone', self.repository, repoPath])
    run(['git', 'checkout', self.commit], cwd=repoPath)

  def getKey(self) -> str:
    return f"{type(self).__name__}({repr(self.repository)},{self.commit})"


class TarBall(Source):
  url: str
  sha256: str

  def __init__(self, url: str, *, sha256: str='') -> None:
    super().__init__()
    self.url = url
    self.sha256 = sha256

  def get(self, repoPath: str) -> None:
    print('TarBall get')
    tmpDirPath = f"{repoPath}.tmp"
    if os.path.exists(repoPath):
      shutil.rmtree(repoPath)
    if os.path.exists(tmpDirPath):
      shutil.rmtree(tmpDirPath)
    os.makedirs(tmpDirPath)

    tarPath = f"{repoPath}.tar.gz"

    with urlopen(self.url) as uf:
      with open(tarPath, 'wb') as tf:
        shutil.copyfileobj(uf, tf)

    if self.sha256:
      m = hashlib.sha256()
      with open(tarPath, 'rb') as f:
        m.update(f.read())
      digest = m.hexdigest()
      if digest != self.sha256:
        raise AssertionError(
          f'TarBall {self.url} sha256 digest does not match')

    # TODO: sanitize tar file extraction
    with tarfile.open(tarPath) as tf:
      tf.extractall(tmpDirPath)

    folderNames = os.listdir(tmpDirPath)
    if len(folderNames) != 1:
      raise Exception(
        f"Tarball expected exactly one top level entry but got: "
        f"{','.join(folderNames)}")
    outFolderPath = os.path.join(tmpDirPath, folderNames[0])
    shutil.move(outFolderPath, repoPath)
    shutil.rmtree(tmpDirPath)


  def getKey(self) -> str:
    return f"{type(self).__name__}({self.url},{self.sha256})"



class BuildStep(ABC):

  @abstractmethod
  def makeInstall(self, repoPath: str) -> None:
    pass

  @abstractmethod
  def getKey(self) -> str:
    pass


class CombinedStep(BuildStep):
  steps: typing.List[BuildStep]

  def __init__(self, *steps: BuildStep) -> None:
    self.steps = list(steps)

  def makeInstall(self, repoPath: str) -> None:
    for step in self.steps:
      step.makeInstall(repoPath)

  def getKey(self) -> str:
    return (
      f'{type(self).__name__}({",".join(s.getKey() for s in self.steps)})')


class SwitchOnPlatform(BuildStep):
  unix: BuildStep
  windows: BuildStep

  def __init__(self, *, unix: BuildStep, windows: BuildStep) -> None:
    self.unix = unix
    self.windows = windows

  def makeInstall(self, repoPath: str) -> None:
    if _windows:
      return self.windows.makeInstall(repoPath)
    return self.unix.makeInstall(repoPath)

  def getKey(self) -> str:
    return (
      f'{type(self).__name__}({self.unix.getKey()},{self.windows.getKey()})')


class ConfigureAndMake(BuildStep):
  additionalConfigureFlags: typing.List[str]

  def __init__(self, additionalConfigureFlags: typing.List[str]) -> None:
    self.additionalConfigureFlags = additionalConfigureFlags

  def makeInstall(self, repoPath: str) -> None:
    run(
      [
        os.path.join(repoPath, 'configure'),
        f'--prefix={PKGS_PATH}',
      ] + self.additionalConfigureFlags,
      cwd=repoPath,
      env={
        'CPPFLAGS': f'-I{PKGS_PATH}/include',
        'LDFLAGS': f'-L{PKGS_PATH}/lib',
        'PATH': f"{os.environ['PATH']}:{PKGS_PATH}/bin",
      })
    run(['make'], cwd=repoPath)
    run(['make', 'install'], cwd=repoPath)

  def getKey(self) -> str:
    return f"{type(self).__name__}({','.join(self.additionalConfigureFlags)})"


class CopyInclude(BuildStep):
  relativeIncludePath: str

  def __init__(self, relativeIncludePath: str) -> None:
    self.relativeIncludePath = relativeIncludePath

  def makeInstall(self, repoPath: str) -> None:
    includePath = os.path.join(repoPath, self.relativeIncludePath)
    dstIncludePath = os.path.join(PKGS_PATH, 'include')

    os.makedirs(dstIncludePath, exist_ok=True)

    for item in os.listdir(includePath):
      itemPath = os.path.join(includePath, item)
      if os.path.isdir(itemPath):
        shutil.copytree(itemPath, os.path.join(dstIncludePath, item))
      else:
        shutil.copy(itemPath, dstIncludePath)
    return super().makeInstall(repoPath)

  def getKey(self) -> str:
    return f'{type(self).__name__}({self.relativeIncludePath})'


class MSBuild(BuildStep):
  relativeProjectPath: str

  def __init__(self, relativeProjectPath: str) -> None:
    self.relativeProjectPath = relativeProjectPath

  def makeInstall(self, repoPath: str) -> None:
    projectPath = os.path.join(repoPath, self.relativeProjectPath)
    artifactsPath = os.path.join(projectPath, 'x64', 'Release')

    run(
      [MSBUILD_SCRIPT_PATH, '/p:Configuration=Release'],
      cwd=projectPath)

    # Copy over outputs
    libDirPath = os.path.join(PKGS_PATH, 'lib')
    binDirPath = os.path.join(PKGS_PATH, 'bin')
    os.makedirs(libDirPath, exist_ok=True)
    os.makedirs(binDirPath, exist_ok=True)

    for fileName in os.listdir(artifactsPath):
      filePath = os.path.join(artifactsPath, fileName)
      if fileName.endswith('.lib'):
        shutil.copy(filePath, libDirPath)
      else:
        shutil.copy(filePath, binDirPath)

  def getKey(self) -> str:
    return f"{type(self).__name__}({self.relativeProjectPath})"

configureAndMake = ConfigureAndMake([])


class Package:
  name: str
  source: Source
  buildStep: BuildStep
  dependencies: typing.List['Package']

  def __init__(
      self,
      name: str,
      source: Source,
      buildStep: BuildStep,
      dependencies: typing.List['Package']) -> None:
    self.name = name
    self.source = source
    self.buildStep = buildStep
    self.dependencies = dependencies
    self.repoPath = os.path.join(REPOS_PATH, self.name)

  def _get(self) -> None:
    self.source.get(self.repoPath)

  def _buildAndInstall(self) -> None:
    self.buildStep.makeInstall(self.repoPath)

  def getKey(self) -> str:
    "Used to check if the given package has already been installed"
    return f"{self.source.getKey()},{self.buildStep.getKey()}"

  def _isInstalled(self) -> bool:
    "Is this specific version of this package currently installed"
    return _installJson.get(self.name, None) == self.getKey()

  def _walkDepTree(
      self,
      seen: typing.Dict['Package', bool],
      alreadyInstalled: typing.List['Package'],
      needToInstall: typing.List['Package']) -> bool:
    if self not in seen:
      seen[self] = False
      depNeedsUpdating = False
      for dep in self.dependencies:
        depNeedsUpdating = (
          dep._walkDepTree(seen, alreadyInstalled, needToInstall)
          or depNeedsUpdating
        )
      if self._isInstalled() and not depNeedsUpdating:
        alreadyInstalled.append(self)
        seen[self] = False
      else:
        needToInstall.append(self)
        seen[self] = True
    return seen[self]

  def install(self):
    needToInstall: typing.List['Package'] = []
    alreadyInstalled: typing.List['Package'] = []
    self._walkDepTree({}, alreadyInstalled, needToInstall)

    for pkg in alreadyInstalled:
      print(f'Skipping {pkg.name} (already installed)')

    for pkg in needToInstall:
      print(f'Installing {pkg.name}')
      pkg._get()
      pkg._buildAndInstall()
      _installJson[pkg.name] = pkg.getKey()
      _saveInstallJson()
      print(f'Package {pkg.name} installed')


packageMap: typing.Dict[str, Package] = {}


def pkg(
    *,
    name: str,
    source: Source,
    buildStep: BuildStep=configureAndMake,
    deps: typing.Iterable[str]=()):

  dependencies: typing.List[Package] = []
  for depName in deps:
    if depName not in packageMap:
      raise NameError(f'Dependency {depName} (for {name}) not found')
    dependencies.append(packageMap[depName])

  packageMap[name] = Package(
    name=name,
    source=source,
    buildStep=buildStep,
    dependencies=dependencies,
  )
