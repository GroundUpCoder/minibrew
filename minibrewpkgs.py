from minibrewlib import (
  pkg, Git, TarBall,
  configureAndMake,
  ConfigureAndMake, SwitchOnPlatform, MSBuild, CombinedStep, CopyInclude,
)


pkg(
  name='sdl',
  source=Git(
    repository='https://github.com/libsdl-org/SDL.git',
    commit='release-2.26.1',
  ),
  buildStep=SwitchOnPlatform(
    unix=configureAndMake,
    windows=CombinedStep(
      CopyInclude('include'),
      MSBuild('VisualC'),
    ),
  ),
)

pkg(
  name='ffmpeg',
  source=Git(
    repository='https://github.com/FFmpeg/FFmpeg.git',
    commit='n5.1.2',
  ),
  deps=['sdl'],
  buildStep=ConfigureAndMake([
    '--enable-sdl',
    '--enable-ffplay',
  ]),
)

pkg(
  name='graphviz',
  source=TarBall(
    'https://gitlab.com/api/v4/projects/4207231/packages/'
    'generic/graphviz-releases/7.0.4/graphviz-7.0.4.tar.gz',
    sha256='3584b950911388bba0c315a34166011324dbd7da1e954b245dd9cf7f521f528f',
  ),
)
