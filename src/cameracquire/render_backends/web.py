from time import time
from queue import Queue
from asyncio import sleep
from enum import Enum
from hypercorn.asyncio import serve
from hypercorn.config import Config

from quart import Quart, Response, render_template, stream_with_context
from . import CrossInstanceCameraAttributes, CrossInstanceReferencer

# from flask import Flask, Response, render_template
import cv2

# app = Flask(__name__.split(".")[0])
app = Quart(__name__)


class LogggingLevels(Enum):

    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


LOGGING_LEVEL = LogggingLevels.INFO.value

INFO_STREAM_RATE = 30  # Infos refresh rate for fps, images captured, etc, on the web page, in Hz


@app.route("/")
async def index():
    if LOGGING_LEVEL <= LogggingLevels.INFO.value:
        print("🆕 Connection to web app 📷")
    return await render_template("./web_template.html")


@app.route("/video_feed")
async def video_feed():
    return stream_response(StreamImage.stream_frames, "multipart/x-mixed-replace; boundary=frame")


@app.route("/stream-fps")
async def stream_fps():
    return stream_response(StreamImage.stream_streamed_fps, "text/event-stream")


@app.route("/image-size")
async def image_size():
    return stream_response(ImageRecievedNotificationRenderer.stream_image_size, "text/event-stream")


@app.route("/images-recieved")
async def images_recieved():
    return stream_response(ImageRecievedNotificationRenderer.stream_images_recieved, "text/event-stream")


@app.route("/real-fps")
async def real_fps():
    return stream_response(ImageRecievedNotificationRenderer.real_fps, "text/event-stream")


async def run_app(host, port):
    config = Config()
    config.bind = [f"{host}:{port}"]
    await serve(app, config)


def stream_response(generator_func, mimetype):
    async def generate():
        try:
            async for data in generator_func():
                yield data
        except GeneratorExit:
            if LOGGING_LEVEL <= LogggingLevels.DEBUG.value:
                print(f"❌ Client disconnected from {generator_func.__name__}")
        except Exception as e:
            if LOGGING_LEVEL <= LogggingLevels.ERROR.value:
                print(f"Dead stream 💀 Exception in {generator_func.__name__}: {type(e)}: {e}")

    if LOGGING_LEVEL <= LogggingLevels.DEBUG.value:
        print(f"🛜 Client connected to {generator_func.__name__}")
    return Response(stream_with_context(generate)(), mimetype=mimetype)


FRAME_QUEUE = Queue(maxsize=3)


class StreamImage:

    MAX_FPS = 30  # in Hz
    last_frame_time: CrossInstanceReferencer[float] = CrossInstanceReferencer(0)
    streamed_frame_times = []
    streamed_fps: CrossInstanceReferencer[float] = CrossInstanceReferencer(0)

    def render(self, image):
        now = time()
        if now - self.last_frame_time.get() < 1 / self.MAX_FPS:  # type: ignore
            return

        self.last_frame_time.set(now)

        _, jpeg = cv2.imencode(".jpg", image)
        frame = jpeg.tobytes()

        if FRAME_QUEUE.full():
            FRAME_QUEUE.get()  # Remove the oldest frame
        FRAME_QUEUE.put(frame)

    @staticmethod
    def set_stream_fps():
        now = time()
        streamed_frame_times = StreamImage.streamed_frame_times
        streamed_frame_times.append(now)
        streamed_frame_times = list(filter(lambda value: value >= now - 1, streamed_frame_times))
        StreamImage.streamed_fps.set(len(streamed_frame_times))
        StreamImage.streamed_frame_times = streamed_frame_times

    @staticmethod
    async def stream_frames():
        while True:
            frame = FRAME_QUEUE.get()
            StreamImage.set_stream_fps()
            try:
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            except Exception as e:
                print(f"Exception in stream_frames: {e}")
                break
            await sleep((1 / StreamImage.MAX_FPS) / 2)

    @staticmethod
    async def stream_streamed_fps():
        while True:
            yield f"data: {StreamImage.streamed_fps.get()}\n\n"
            await sleep(1 / INFO_STREAM_RATE)


class ImageRecievedNotificationRenderer:

    MEMORY = CrossInstanceCameraAttributes()

    def render(self, image_shape):
        self.MEMORY.update(image_shape)

    @staticmethod
    async def real_fps():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.real_fps}\n\n"
            await sleep(1 / INFO_STREAM_RATE)

    @staticmethod
    async def stream_images_recieved():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.total_frames}\n\n"
            await sleep(1 / INFO_STREAM_RATE)

    @staticmethod
    async def stream_image_size():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.image_shape}\n\n"
            await sleep(1 / INFO_STREAM_RATE)
