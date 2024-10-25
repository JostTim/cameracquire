from time import time
from queue import Queue
from asyncio import sleep

from hypercorn.asyncio import serve
from hypercorn.config import Config

from quart import Quart, Response, render_template, stream_with_context
from . import CrossInstanceCameraAttributes, CrossInstanceReferencer

# from flask import Flask, Response, render_template
import cv2

# app = Flask(__name__.split(".")[0])
app = Quart(__name__)


@app.route("/")
async def index():
    return await render_template("./web_template.html")


@app.route("/video_feed")
async def video_feed():
    return Response(
        stream_with_context(StreamImage.stream_frames)(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/real_fps")
async def real_fps():
    return Response(stream_with_context(ImageRecievedNotificationRenderer.stream_fps)(), mimetype="text/event-stream")


async def run_app(host, port):
    config = Config()
    config.bind = [f"{host}:{port}"]
    await serve(app, config)


FRAME_QUEUE = Queue(maxsize=3)


class StreamImage:

    MAX_FPS = 30
    last_frame_time: CrossInstanceReferencer[float] = CrossInstanceReferencer(0)
    streamed_frame_times = []
    streamed_fps: CrossInstanceReferencer[float] = CrossInstanceReferencer(0)

    def render(self, image):
        now = time()
        if now - self.last_frame_time.get() < 1 / self.MAX_FPS:  # type: ignore
            return

        self.streamed_frame_times.append(now)
        self.streamed_frame_times = list(filter(lambda value: value >= now - 1, self.streamed_frame_times))
        self.streamed_fps.set(len(self.streamed_frame_times))

        self.last_frame_time.set(now)

        _, jpeg = cv2.imencode(".jpg", image)
        frame = jpeg.tobytes()

        if FRAME_QUEUE.full():
            FRAME_QUEUE.get()  # Remove the oldest frame
        FRAME_QUEUE.put(frame)

    @staticmethod
    async def stream_frames():
        while True:
            frame = FRAME_QUEUE.get()
            try:
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            except Exception as e:
                print(f"Exception in stream_frames: {e}")
                break

    @staticmethod
    async def stream_images_recieved():
        while True:
            yield f"data: {StreamImage.streamed_fps.get()}\n\n"
            await sleep(1)


class ImageRecievedNotificationRenderer:

    MEMORY = CrossInstanceCameraAttributes()

    def render(self, image_shape):
        self.MEMORY.update(image_shape)

    @staticmethod
    async def stream_fps():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.real_fps}\n\n"
            await sleep(1)

    @staticmethod
    async def stream_images_recieved():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.total_frames}\n\n"
            await sleep(1)

    @staticmethod
    async def stream_image_size():
        while True:
            yield f"data: {ImageRecievedNotificationRenderer.MEMORY.image_shape}\n\n"
            await sleep(1)
