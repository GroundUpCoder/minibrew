from abc import ABC, abstractmethod
import typing
import os
import subprocess
import json
import shutil
import hashlib

MINIBREW_PATH = os.path.dirname(os.path.realpath(__file__))
REPOS_PATH = os.path.join(MINIBREW_PATH, 'repos')
PKGS_PATH = os.path.join(MINIBREW_PATH, 'pkgs')
INSTALL_JSON_PATH = os.path.join(PKGS_PATH, 'install.json')


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
    tmpDirPath = os.path.join(REPOS_PATH, f"{repoPath}.tmp")
    if os.path.exists(repoPath):
      shutil.rmtree(repoPath)
    if os.path.exists(tmpDirPath):
      shutil.rmtree(tmpDirPath)
    os.makedirs(tmpDirPath)
    tarPath = f"{repoPath}.tar.gz"
    run(['curl', self.url, '-o', tarPath], cwd=REPOS_PATH)

    if self.sha256:
      m = hashlib.sha256()
      with open(os.path.join(REPOS_PATH, tarPath), 'rb') as f:
        m.update(f.read())
      digest = m.hexdigest()
      if digest != self.sha256:
        raise AssertionError(
          f'TarBall {self.url} sha256 digest does not match')

    run(['tar', 'zxvf', tarPath, '-C', tmpDirPath], cwd=REPOS_PATH)
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



class BuildSteps(ABC):

  @abstractmethod
  def makeInstall(self, repoPath: str) -> None:
    pass

  @abstractmethod
  def getKey(self) -> str:
    pass


class ConfigureAndMake(BuildSteps):
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


configureAndMake = ConfigureAndMake([])


class Package:
  name: str
  source: Source
  buildSteps: BuildSteps
  dependencies: typing.List['Package']

  def __init__(
      self,
      name: str,
      source: Source,
      buildSteps: BuildSteps,
      dependencies: typing.List['Package']) -> None:
    self.name = name
    self.source = source
    self.buildSteps = buildSteps
    self.dependencies = dependencies
    self.repoPath = os.path.join(REPOS_PATH, self.name)

  def _get(self) -> None:
    self.source.get(self.repoPath)

  def _buildAndInstall(self) -> None:
    self.buildSteps.makeInstall(self.repoPath)

  def getKey(self) -> str:
    "Used to check if the given package has already been installed"
    return f"{self.source.getKey()},{self.buildSteps.getKey()}"

  def _isInstalled(self) -> bool:
    "Is this specific version of this package currently installed"
    return _installJson.get(self.name, None) == self.getKey()

  def _walkDepTree(
      self,
      seen: typing.Set['Package'],
      alreadyInstalled: typing.List['Package'],
      needToInstall: typing.List['Package']):
    if self not in seen:
      seen.add(self)
      if self._isInstalled():
        alreadyInstalled.append(self)
      else:
        for dep in self.dependencies:
          dep._walkDepTree(seen, alreadyInstalled, needToInstall)
        needToInstall.append(self)

  def install(self):
    needToInstall: typing.List['Package'] = []
    alreadyInstalled: typing.List['Package'] = []
    self._walkDepTree(set(), alreadyInstalled, needToInstall)

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
    buildSteps: BuildSteps=configureAndMake,
    deps: typing.Iterable[str]=()):

  dependencies: typing.List[Package] = []
  for depName in deps:
    if depName not in packageMap:
      raise NameError(f'Dependency {depName} (for {name}) not found')
    dependencies.append(packageMap[depName])

  packageMap[name] = Package(
    name=name,
    source=source,
    buildSteps=buildSteps,
    dependencies=dependencies,
  )
