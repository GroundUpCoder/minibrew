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
    unix=ConfigureAndMake([
      '--disable-system-iconv',
    ]),
    windows=CombinedStep(
      CopyInclude('include'),
      MSBuild('VisualC'),
    ),
  ),
)

pkg(
  name='freetype',
  source=TarBall(
    # This is the version that homebrew is currently using as of Jan 4, 2023
    'https://download.savannah.gnu.org/releases/freetype/freetype-2.12.1.tar.xz',
  ),
  buildStep=ConfigureAndMake([
    '--enable-freetype-config',
    '--without-harfbuzz',
  ]),
)

pkg(
  name='libpng',
  source=TarBall(
    # This is the version that homebrew is currently using as of Jan 4, 2023
    'https://downloads.sourceforge.net/project/libpng/libpng16/1.6.39/libpng-1.6.39.tar.xz',
  ),
  buildStep=ConfigureAndMake([
    '--disable-dependency-tracking',
    '--disable-silent-rules',
  ]),
)

# TODO: comparing with homebrew, I don't have all the deps yet.
# Currently broken
pkg(
  name='sdl_ttf',
  source=TarBall(
    'https://github.com/libsdl-org/SDL_ttf/archive/refs/tags/release-2.20.1.tar.gz',
  ),
  buildStep=SwitchOnPlatform(
    unix=ConfigureAndMake([
    ]),
    windows=CombinedStep(
      CopyInclude('include'),
      MSBuild('VisualC'),
    ),
  ),
  deps=['freetype', 'sdl', 'libpng'],
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
