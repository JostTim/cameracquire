from pathlib import Path
import numpy as np

from harvesters.core import Harvester, DeviceInfo, ImageAcquirer, Buffer, Component2DImage, ParameterSet, PayloadImage
from genicam.gentl import AccessDeniedException, TimeoutException
from genicam.genapi import ICommand, IEnumeration, IInteger, IBoolean

from typing import List, Dict, Optional
import sys

from .render_backends import get_backends

# download latest GenTL producer .exe from http://static.matrix-vision.com/mvIMPACT_Acquire/
# install, and find it in C:\Program Files\Balluff\ImpactAcquire\bin\x64

CTI_POSSIBLE_LOCATIONS = [
    "C:/Program Files/Teledyne/Spinnaker/cti64/vs2015/Spinnaker_GenTL_v140.cti",
    "C:/Program Files/Balluff/ImpactAcquire/bin/x64/mvGenTLProducer.cti",
    "C:/Program Files/MATRIX VISION/ImpactAcquire/bin/x64/mvGenTLProducer.cti",
]


class CameraDriver(Harvester):

    cti_search_locations = [Path(install_location) for install_location in CTI_POSSIBLE_LOCATIONS]

    def __init__(self, *args, verbose=True, render_backends: Optional[List[str]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = verbose
        self.render_backends = get_backends(render_backends)

    def __enter__(self):
        self = super().__enter__()
        self.get_genicam_driver_location()  # finds the proper genicam driver.
        # Needs to be installed, if not installed will provide a usefull message
        self.update()  # update devices infos
        return self

    def get_genicam_driver_location(self) -> None:

        for cti_file in self.cti_search_locations:
            if cti_file.is_file():
                self.add_file(str(cti_file), check_existence=True, check_validity=True)
                break

        self.render_backends.render("DriverCTIRenderer", self)

        if not len(self._cti_files):
            # if no file is found, we stop the code here
            sys.exit()

    def check_cameras(self) -> Dict[str, DeviceInfo]:

        device_info_list = self.device_info_list if self.device_info_list else []
        cameras = {device.property_dict["id_"]: device for device in device_info_list}
        self.render_backends.render("DeviceInfoRenderer", cameras)
        return cameras

    def select_camera(self, camera_id_number) -> DeviceInfo:
        devices = self.check_cameras()
        device = devices.get(camera_id_number, None)
        self.render_backends.render("DeviceSelectionRenderer", devices, device, camera_id_number)
        if device is None:
            sys.exit()
        return device

    def create(
        self, search_key: int | Dict[str, str] | DeviceInfo | None = None, *, config: ParameterSet | None = None
    ) -> ImageAcquirer:

        try:
            return super().create(search_key, config=config)
        except AccessDeniedException as exception:
            self.render_backends.render("DeviceDeniedAccessRenderer", exception, search_key)
            sys.exit()

    def execute_command(self, acquirer: ImageAcquirer, command=""):

        starter: ICommand = acquirer.remote_device.node_map.get_node(command)
        starter.execute()

    def select_user_set(self, acquirer: ImageAcquirer, user_set=0):

        selector: IEnumeration = acquirer.remote_device.node_map.get_node("UserSetSelector")
        loader: ICommand = acquirer.remote_device.node_map.get_node("UserSetLoad")
        selector.set_int_value(user_set)
        loader.execute()

    def set_free_run(self, acquirer: ImageAcquirer):

        free_runner: IEnumeration = acquirer.remote_device.node_map.get_node("TriggerMode")
        free_runner.set_value("Off")

        acquisition_mode: IEnumeration = acquirer.remote_device.node_map.get_node("AcquisitionMode")
        acquisition_mode.set_value("Continuous")

    def set_high_sensibility(self, acquirer: ImageAcquirer):

        height: IInteger = acquirer.remote_device.node_map.get_node("Height")
        width: IInteger = acquirer.remote_device.node_map.get_node("Width")

        offset_x: IInteger = acquirer.remote_device.node_map.get_node("OffsetX")
        offset_y: IInteger = acquirer.remote_device.node_map.get_node("OffsetY")

        binning: IInteger = acquirer.remote_device.node_map.get_node("BinningVertical")

        binning.set_value(2)

        offset_x.set_value(0)
        offset_y.set_value(0)

        height.set_value(512)
        width.set_value(640)

    def set_low_sensibility(self, acquirer: ImageAcquirer):

        height: IInteger = acquirer.remote_device.node_map.get_node("Height")
        width: IInteger = acquirer.remote_device.node_map.get_node("Width")

        offset_x: IInteger = acquirer.remote_device.node_map.get_node("OffsetX")
        offset_y: IInteger = acquirer.remote_device.node_map.get_node("OffsetY")

        binning: IInteger = acquirer.remote_device.node_map.get_node("BinningVertical")

        binning.set_value(1)

        offset_x.set_value(0)
        offset_y.set_value(0)

        height.set_value(1024)
        width.set_value(1280)

    def activate_chunk_mode(self, acquirer: ImageAcquirer):

        chunk_activator: IBoolean = acquirer.remote_device.node_map.get_node("ChunkModeActive")
        chunk_selector: IEnumeration = acquirer.remote_device.node_map.get_node("ChunkSelector")
        chunk_enabler: IBoolean = acquirer.remote_device.node_map.get_node("ChunkEnable")

        chunk_activator.set_value(True)
        chunk_selector.set_int_value(13)
        chunk_enabler.set_value(True)

    def acquire(self, camera_id_number: str):

        device = self.select_camera(camera_id_number)

        with self.create(device) as acquirer:

            self.set_free_run(acquirer)
            self.set_low_sensibility(acquirer)

            self.select_user_set(acquirer, 0)

            self.activate_chunk_mode(acquirer)

            acquirer.start(run_as_thread=False)

            active = True

            while active:
                try:
                    buffer: Buffer | None = acquirer.fetch(timeout=2, cycle_s=0.1)  # type: ignore
                    exc = None
                except TimeoutException as exc:
                    self.render_backends.render("NoDataRenderer", exc)
                    active = False

                if buffer is None:
                    self.render_backends.render("NoDataRenderer")
                    continue

                payload: PayloadImage = buffer.payload  # type: ignore
                if payload is None:
                    self.render_backends.render("PayloadEmptyRenderer")
                    continue

                self.render_backends.render("PayloadComponentsRenderer", payload)

                image_data: Component2DImage = payload.components[0]  # type: ignore
                if image_data.data is None:
                    self.render_backends.render("PayloadComponentEmptyRenderer")
                    continue

                image = np.reshape(image_data.data, (image_data.height, image_data.width))
                self.render_backends.render("ImageRecievedNotificationRenderer", image.shape)
                # self.render_backends.render("StreamImage", image)

        self.render_backends.render("AcquisitionStoppedRenderer")

    def show_available_nodes(self, camera_id_number: str, exclude_unaccessibles=True):

        device = self.select_camera(camera_id_number)
        with self.create(device) as acquirer:
            self.render_backends.render("NodeRenderer", acquirer)


# class Camera:

#     def __init__(self, driver: CameraDriver, camera_id):

#         self.driver = driver


def simple_test():

    from rich.console import Console

    with Harvester() as h:
        h.add_cti_file("C:/Program Files/Teledyne/Spinnaker/cti64/vs2015/Spinnaker_GenTL_v140.cti")
        h.update()

        c = Console()

        # device_id = "USB\VID_1E10&PID_3300&MI_00\9&2356BD5B&0&0000_0"
        device = [device for device in h.device_info_list][0]

        c.print(f"Device : {device}")

        with h.create(device) as a:

            while True:

                a.start(run_as_thread=False)
                images_to_acquire = "infinite" if a._num_images_to_acquire == -1 else a._num_images_to_acquire
                c.print(f"Nb of images to acquire : {images_to_acquire}")

                timeouted = False

                while not timeouted:
                    try:
                        buffer: Buffer | None = a.fetch(timeout=1)  # type: ignore
                    except TimeoutException:
                        c.print("Timeout", style="bright_red")
                        timeouted = True
                        continue

                    if buffer is None:
                        continue

                    with buffer:
                        image_data: Component2DImage = buffer.payload.components[0]  # type: ignore

                        if image_data.data is None:
                            continue
                        image = np.reshape(image_data.data, (image_data.height, image_data.width))

                        c.print(f"Image shape : {image.shape} at time : {buffer.timestamp}")
                    # buffer.queue()

                a.stop()


# The buffer.queue() method is used to return a buffer to the acquisition engine's queue after it has been processed.
# Here's a brief explanation of its purpose:

# Buffer Management: When a camera captures an image, it places the image data into a buffer.
# These buffers are part of a pool managed by the acquisition engine.

# Releasing Buffers: After you process the image data from a buffer,
# you need to release the buffer back to the pool so it can be reused for future image captures.
# This is what buffer.queue() does—it requeues the buffer, making it available for the next image acquisition.

# Preventing Buffer Exhaustion: If buffers are not requeued, the system will eventually run out of available buffers,
# leading to timeouts and acquisition failures. Properly queuing buffers ensures a continuous and efficient
# image acquisition process.

# By calling buffer.queue(), you ensure that the buffer is returned to the pool, preventing buffer exhaustion and
# maintaining a smooth acquisition workflow.
