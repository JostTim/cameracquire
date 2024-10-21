from flask import Flask, Response, render_template_string
from queue import Queue
import cv2

app = Flask(__name__.split(".")[0])

FRAME_QUEUE = Queue(maxsize=10)


class StreamImage:

    def render(self, image):

        _, jpeg = cv2.imencode(".jpg", image)
        frame = jpeg.tobytes()

        if not FRAME_QUEUE.full():
            FRAME_QUEUE.put(frame)


def generate_frames():
    while True:
        frame = FRAME_QUEUE.get()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
