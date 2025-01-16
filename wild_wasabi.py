import argparse
from src.wasabi import Wasabi

def main():
    parser = argparse.ArgumentParser(description="none")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-e", "--err", action="store_true")
    parser.add_argument("-t", "--threads", action="store", default=10)

    subparsers = parser.add_subparsers(dest="command")
    file_parser = subparsers.add_parser("file")
    dir_parser = subparsers.add_parser("dir")

    file_parser.add_argument("-p", "--path", action="store")
    file_parser.add_argument("-r", "--regex", action="store")
    file_parser.add_argument("-c", "--contains", action="store")

    dir_parser.add_argument("-p", "--path", action="store")
    dir_parser.add_argument("-r", "--regex", action="store")
    dir_parser.add_argument("-c", "--contains", action="store")
    dir_parser.add_argument("-R", "--recursive", action="store_true")
    dir_parser.add_argument("-o", "--open-files", action="store_true", help="Read file contents")
    dir_parser.add_argument("-n", "--names", action="store_true", help="list file names")

    args = parser.parse_args()
    wasabi = Wasabi(
        debug=args.debug,
        threads=args.threads,
        regex=args.regex,
        rx_contains=args.contains,
        disable_errors=args.err,
        recursive=args.recursive
    )

    if args.command == "file":
        wasabi.parse_file(args)
    elif args.command == "dir":
        wasabi.parse_directory(args)
    else:
        print(f"Error: {args.command} is not a valid subcommand")
        return

if __name__ == "__main__":
    main()