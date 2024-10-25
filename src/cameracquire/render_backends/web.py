from time import time
from queue import Queue
from asyncio import sleep

from quart import Quart, Response, render_template, stream_with_context

from . import CrossInstanceCameraAttributes

# from flask import Flask, Response, render_template
import cv2

# app = Flask(__name__.split(".")[0])
app = Quart(__name__)

FRAME_QUEUE = Queue(maxsize=10)


class StreamImage:

    def render(self, image):

        _, jpeg = cv2.imencode(".jpg", image)
        frame = jpeg.tobytes()

        if not FRAME_QUEUE.full():
            FRAME_QUEUE.put(frame)

    @staticmethod
    async def stream_frames():
        while True:
            frame = FRAME_QUEUE.get()
            yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")


class ShowFrameRate:

    MEMORY = CrossInstanceCameraAttributes()

    def render(self):
        self.MEMORY.add_frame_and_get_fps()

    @staticmethod
    async def stream_fps():
        while True:
            yield f"{ShowFrameRate.MEMORY.real_fps}"
            await sleep(1)


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
    return Response(stream_with_context(ShowFrameRate.stream_fps)())
