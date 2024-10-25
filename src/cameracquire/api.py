from .core import CameraDriver
from .render_backends import register_backend

import argparse


def acquire(args):

    if args.stream:
        from .render_backends import web
        from webbrowser import open_new as open_new_webbrowser
        from threading import Timer, Thread

        host = "127.0.0.1"
        port = 5678
        register_backend("web", web)

        def open_browser():
            open_new_webbrowser(f"http://{host}:{port}/")

        def run_flask_app():
            web.app.run(host=host, port=port, debug=False)

        flask_thread = Thread(target=run_flask_app)
        flask_thread.start()

        Timer(1, open_browser).start()

    with CameraDriver() as driver:
        driver.acquire(args.id)


def list_cameras(args):
    with CameraDriver() as driver:
        driver.check_cameras()


def list_nodes(args):
    with CameraDriver() as driver:
        device = driver.select_camera(args.id)
        with driver.create(device) as acquirer:
            driver.render_backends.render("NodeRenderer", acquirer)


def test(args):
    from .core import simple_test

    simple_test()


def command_dispatcher():

    from .render_backends import terminal
    from .render_backends import register_backend

    register_backend("rich", terminal)

    parser = argparse.ArgumentParser(description="Camera acquisition commands")
    subparsers = parser.add_subparsers(dest="command")

    parser_list_cameras = subparsers.add_parser("list-cameras", help="List all available cameras")
    parser_list_cameras.set_defaults(func=list_cameras)

    parser_start = subparsers.add_parser("start", help="Start acquiring images from a camera")
    parser_start.set_defaults(func=acquire)
    parser_start.add_argument(
        "--id",
        "-i",
        type=str,
        help="ID naming of the camera. Can be obtained with command list-cameras",
        required=True,
    )
    parser_start.add_argument(
        "--stream", "-s", action="store_true", help="Wether to stream images with decimation on the WEB API"
    )

    parser_list_nodes = subparsers.add_parser("list-nodes", help="List all available nodes for the selected camera")
    parser_list_nodes.add_argument(
        "--id", "-i", type=str, help="ID naming of the camera. Can be obtained with command list-cameras"
    )
    parser_list_nodes.set_defaults(func=list_nodes)

    parser_test = subparsers.add_parser("test", help="Test acquring images from a camera")
    parser_test.set_defaults(func=test)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
    else:
        args.func(args)
