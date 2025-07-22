#!/usr/bin/env python3
# -- coding: utf-8 --

import os
import sys
import threading
import time
import logging
from ctypes import *
import numpy as np
import cv2
from flask import Flask, Response
from typing import Optional

if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(r"C:\Program Files\HuarayTech\MV Viewer\Runtime\x64")

sys.path.append("/opt/HuarayTech/MVviewer/share/Python/MVSDK")
from IMVApi import *

class IraypleStreamer:
    def __init__(self, ip: str, log=None):
        self.ip = ip
        self.cam = None
        self._last_frame = None
        self.lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()

        if log:
            self.logger = log
        else:
            self.logger = logging.getLogger(f"{__name__}.IraypleStreamer")
            if not self.logger.handlers:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s"
                ))
                self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self._cb_type = CFUNCTYPE(None, POINTER(IMV_Frame), c_void_p)
        self._cb_fun = self._cb_type(self._image_callback)

        self._open_camera()

    def _open_camera(self):
        devList = IMV_DeviceList()
        if MvCamera.IMV_EnumDevices(devList, IMV_EInterfaceType.interfaceTypeAll) != IMV_OK:
            raise RuntimeError("Errore enumerazione device")

        idx = None
        for i in range(devList.nDevNum):
            info = devList.pDevInfo[i].DeviceSpecificInfo.gigeDeviceInfo
            if info.ipAddress.decode() == self.ip:
                idx = i
                break
        if idx is None:
            raise ValueError(f"Nessuna camera trovata con IP {self.ip}")
        self.logger.info(f"Camera trovata all'indice {idx} (IP: {self.ip})")

        self.cam = MvCamera()
        handle_index = c_void_p(idx)
        self.cam.IMV_CreateHandle(IMV_ECreateHandleMode.modeByIndex, byref(handle_index))
        self.cam.IMV_Open()

        feature = "BalanceWhiteAutoReg"
        value_continuous = 2
        value_once = 1

        if self.cam.IMV_FeatureIsAvailable(feature) and self.cam.IMV_FeatureIsWriteable(feature):
            ret = self.cam.IMV_SetIntFeatureValue(feature, value_once)
            if ret == IMV_OK:
                self.logger.info(f"{feature} impostato a {value_once} (Once)")
            else:
                self.logger.error(f"Errore IMV_SetIntFeatureValue({feature}): {ret}")
        else:
            self.logger.warning(f"{feature} non disponibile o non scrivibile")

        self.cam.IMV_SetEnumFeatureSymbol("TriggerSource", "Software")
        self.cam.IMV_SetEnumFeatureSymbol("TriggerSelector", "FrameStart")
        self.cam.IMV_SetEnumFeatureSymbol("TriggerMode", "Off")

        self.cam.IMV_AttachGrabbing(self._cb_fun, None)

    def _image_callback(self, pFrame, pUser):
        if not pFrame:
            return
        frame = cast(pFrame, POINTER(IMV_Frame)).contents

        stParam = IMV_PixelConvertParam()
        mono = frame.frameInfo.pixelFormat == IMV_EPixelType.gvspPixelMono8
        dstSize = frame.frameInfo.width * frame.frameInfo.height * (1 if mono else 3)
        pDstBuf = (c_ubyte * dstSize)()
        memset(byref(stParam), 0, sizeof(stParam))
        stParam.nWidth = frame.frameInfo.width
        stParam.nHeight = frame.frameInfo.height
        stParam.ePixelFormat = frame.frameInfo.pixelFormat
        stParam.pSrcData = frame.pData
        stParam.nSrcDataLen = frame.frameInfo.size
        stParam.nPaddingX = frame.frameInfo.paddingX
        stParam.nPaddingY = frame.frameInfo.paddingY
        stParam.eBayerDemosaic = IMV_EBayerDemosaic.demosaicNearestNeighbor
        stParam.eDstPixelFormat = frame.frameInfo.pixelFormat
        stParam.pDstBuf = pDstBuf
        stParam.nDstBufSize = dstSize

        self.cam.IMV_ReleaseFrame(frame)

        if mono:
            buf = (c_ubyte * dstSize)()
            memmove(buf, stParam.pSrcData, dstSize)
            img = np.frombuffer(buf, dtype=np.uint8).reshape(
                stParam.nHeight, stParam.nWidth
            )
        else:
            stParam.eDstPixelFormat = IMV_EPixelType.gvspPixelBGR8
            if self.cam.IMV_PixelConvert(stParam) != IMV_OK:
                return
            buf = (c_ubyte * dstSize)()
            memmove(buf, stParam.pDstBuf, dstSize)
            img = np.frombuffer(buf, dtype=np.uint8).reshape(
                stParam.nHeight, stParam.nWidth, 3
            )

        with self.lock:
            self._last_frame = img.copy()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        self.logger.info("Thread di grabbing avviato")

    def _grab_loop(self):
        nRet = self.cam.IMV_StartGrabbing()
        if nRet != IMV_OK:
            raise RuntimeError(f"StartGrabbing failed: {nRet}")
        self.logger.info("Grabbing avviato")
        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        finally:
            self.cam.IMV_StopGrabbing()
            self.logger.info("Grabbing fermato")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        if self.cam:
            self.cam.IMV_CloseDevice()
            self.cam.IMV_DestroyHandle()
        self.logger.info("Camera fermata e risorse liberate")

    def stream_response(self):
        def gen():
            while True:
                with self.lock:
                    frame = self._last_frame
                if frame is None:
                    continue
                ok, jpg = cv2.imencode('.jpg', frame)
                if not ok:
                    self.logger.warning("JPEG encode fallito")
                    continue
                data = jpg.tobytes()
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(data)).encode() + b'\r\n'
                    b'\r\n' + data + b'\r\n'
                )
                time.sleep(0.03)
        return Response(
            gen(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )

    def read(self) -> Optional[bytes]:
        with self.lock:
            frame = self._last_frame
        if frame is None:
            self.logger.warning("No frame available yet")
            return None
        ok, buf = cv2.imencode('.jpg', frame)
        if not ok:
            self.logger.warning("JPEG encode fallito")
            return None
        return buf.tobytes()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
