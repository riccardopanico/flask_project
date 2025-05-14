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

# Se serve Windows DLL path
if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(r"C:\Program Files\HuarayTech\MV Viewer\Runtime\x64")

# SDK HuarayTech
sys.path.append("/opt/HuarayTech/MVviewer/share/Python/MVSDK")
from IMVApi import *

class IraypleStreamer:
    def __init__(self, ip: str, log=None):
        """
        ip: indirizzo IP della camera da selezionare automaticamente
        log: logger esterno (es. app.logger); se None, se ne crea uno interno
        """
        self.ip = ip
        self.cam = None
        self.output_frame = None
        self.lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()

        # Logger: usa quello passato o ne crea uno semplice
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

        # Callback C
        self._cb_type = CFUNCTYPE(None, POINTER(IMV_Frame), c_void_p)
        self._cb_fun = self._cb_type(self._image_callback)

        self._open_camera()

    def _open_camera(self):
        # 1) Enumerazione device
        devList = IMV_DeviceList()
        if MvCamera.IMV_EnumDevices(devList, IMV_EInterfaceType.interfaceTypeAll) != IMV_OK:
            raise RuntimeError("Errore enumerazione device")

        # 2) Cerca device con IP corrispondente
        idx = None
        for i in range(devList.nDevNum):
            info = devList.pDevInfo[i].DeviceSpecificInfo.gigeDeviceInfo
            if info.ipAddress.decode() == self.ip:
                idx = i
                break
        if idx is None:
            raise ValueError(f"Nessuna camera trovata con IP {self.ip}")
        self.logger.info(f"Camera trovata all'indice {idx} (IP: {self.ip})")

        # 3) Crea handle e apri
        self.cam = MvCamera()
        handle_index = c_void_p(idx)
        self.cam.IMV_CreateHandle(IMV_ECreateHandleMode.modeByIndex, byref(handle_index))
        self.cam.IMV_Open()

        ## Settaggio autobalance white
        feature = "BalanceWhiteAutoReg"
        value_continuous = 2  # l'enum Continuous ha Value=2 

        # controlli
        if self.cam.IMV_FeatureIsAvailable(feature) and self.cam.IMV_FeatureIsWriteable(feature):
            ret = self.cam.IMV_SetIntFeatureValue(feature, value_continuous)
            if ret == IMV_OK:
                print(f"{feature} impostato a {value_continuous} (Continuous)")
            else:
                print(f"Errore IMV_SetIntFeatureValue({feature}):", ret)
        else:
            print(f"{feature} non disponibile o non scrivibile")
        ## fine settaggio

        # 4) Configura trigger software
        self.cam.IMV_SetEnumFeatureSymbol("TriggerSource", "Software")
        self.cam.IMV_SetEnumFeatureSymbol("TriggerSelector", "FrameStart")
        self.cam.IMV_SetEnumFeatureSymbol("TriggerMode", "Off")

        # 5) Attacca callback
        self.cam.IMV_AttachGrabbing(self._cb_fun, None)

    def _image_callback(self, pFrame, pUser):
        if not pFrame:
            return
        frame = cast(pFrame, POINTER(IMV_Frame)).contents

        # Parametri conversione
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

        # Rilascia subito la memoria driver
        self.cam.IMV_ReleaseFrame(frame)

        # Costruisci numpy array
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

        # Salva frame
        with self.lock:
            self.output_frame = img.copy()

    def start(self):
        """Avvia il thread di grabbing."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()
        self.logger.info("Thread di grabbing avviato")

    def _grab_loop(self):
        # Avvia grabbing
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
        """Ferma il grabbing e pulisce le risorse."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        self.cam.IMV_CloseDevice()
        self.cam.IMV_DestroyHandle()
        self.logger.info("Camera fermata e risorse liberate")

    def stream_response(self):
        """Restituisce un Flask Response con MJPEG stream."""
        def gen():
            while True:
                with self.lock:
                    frame = self.output_frame
                if frame is None:
                    continue
                ok, jpg = cv2.imencode('.jpg', frame)
                if not ok:
                    self.logger.warning("JPEG encode fallito")
                    continue
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' +
                       jpg.tobytes() + b'\r\n')
                time.sleep(0.03)
        return Response(gen(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
