from .core import CameraDriver
from .render_backends import register_backend
import asyncio
import argparse


def acquire(args):

    if args.stream:
        # from .render_backends import web
        # from webbrowser import open_new as open_new_webbrowser
        # from asyncio import get_event_loop

        # host = "127.0.0.1"
        # port = 5678
        # register_backend("web", web)

        # def open_browser():
        #     open_new_webbrowser(f"http://{host}:{port}/")

        # loop = get_event_loop()
        # loop.create_task(web.run_app(host, port))

        # loop.call_later(1, open_browser)
        # loop.call_later(1, print, "Opened the browser page")

        # print(f"Started web app in {loop}")
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(run_streamed_acquisition(args))
        except KeyboardInterrupt:
            print("Acquisition stopped by user.")
        finally:
            # Cancel all running tasks
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()

    else:
        with CameraDriver() as driver:
            driver.acquire(args.id)


async def run_streamed_acquisition(args):
    # Run both the web app and camera acquisition concurrently
    await asyncio.gather(run_web_app(), run_camera_acquisition(args.id))


async def run_web_app():
    from .render_backends import web
    from webbrowser import open_new as open_new_webbrowser
    from asyncio import get_event_loop

    host = "127.0.0.1"
    port = 5678
    register_backend("web", web)

    def open_browser():
        open_new_webbrowser(f"http://{host}:{port}/")

    loop = get_event_loop()
    web_task = loop.create_task(web.run_app(host, port))

    loop.call_later(1, open_browser)
    loop.call_later(1, print, "Opened the browser page")

    try:
        await web_task
    except asyncio.CancelledError:
        print("Web app task cancelled.")


async def run_camera_acquisition(camera_id):
    # Run the camera acquisition in an executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    with CameraDriver() as driver:
        await loop.run_in_executor(None, driver.acquire, camera_id)


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
