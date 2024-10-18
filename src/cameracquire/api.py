from .core import CameraDriver
from .render_backends.terminal import NodeRenderer
import argparse


def acquire(args):
    with CameraDriver() as driver:
        driver.acquire(args.id)


def list_cameras(args):
    with CameraDriver() as driver:
        driver.check_cameras()


def list_nodes(args):
    with CameraDriver() as driver:
        device = driver.select_camera(args.id)
        with driver.create(device) as acquirer:
            NodeRenderer(exclude_unaccessible_nodes=True).print_camera_nodes(acquirer)


def command_dispatcher():
    parser = argparse.ArgumentParser(description="Camera acquisition commands")
    subparsers = parser.add_subparsers(dest="command")

    parser_list_cameras = subparsers.add_parser("list-cameras", help="List all available cameras")
    parser_list_cameras.set_defaults(func=list_cameras)

    parser_start = subparsers.add_parser("start", help="Start acquiring images from a camera")
    parser_start.set_defaults(func=acquire)
    parser_start.add_argument(
        "-i",
        "--id",
        type=str,
        help="ID naming of the camera. Can be obtained with command list-cameras",
        required=True,
    )

    parser_list_nodes = subparsers.add_parser("list-nodes", help="List all available nodes for the selected camera")
    parser_list_nodes.add_argument(
        "-i", "--id", type=str, help="ID naming of the camera. Can be obtained with command list-cameras"
    )
    parser_list_nodes.set_defaults(func=list_nodes)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        args.func(args)
