import minibrewpkgs
import minibrewlib as lib
import argparse


commands = (
  'install',
)


aparser = argparse.ArgumentParser()
subparsers = aparser.add_subparsers(title='command')
subparser_install = subparsers.add_parser('install')
subparser_install.set_defaults(command='install')
subparser_install.add_argument('target')

def main():
  args = aparser.parse_args()
  command: str = args.command
  if command == 'install':
    targetName: str = args.target
    if targetName not in lib.packageMap:
      raise Exception(f'Target name {targetName} not found')
    target = lib.packageMap[targetName]
    target.install()
  else:
    raise Exception(f'Unrecognized command {command}')


if __name__ == '__main__':
  main()
