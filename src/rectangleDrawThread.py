from PyQt5.QtGui import *
from cv2 import *
import threading
import time
from PyQt5.QtGui import QPixmap
import tools_matrix as tools
import numpy as np
import imutils

class rectangleThread(threading.Thread):  # 继承父类threading.Thread
    def __init__(self, threadID,frame,lock):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.frame = frame
        self.preTime = 0
        self.threshold = [0.6, 0.6, 0.7]
        self.lock = lock
    def run(self):  # 把要执行的代码写到run函数里面 线程在创建后会直接运行run函数
        self.lock.acquire()
        time.sleep(1)
        print("12")
        # self.lock.acquire()
        # rectangles = self.detectFace(self.frame, self.threshold)
        # frame = self.rectangleDraw(rectangles, self.frame)
        self.lock.release()
    def detectFace(self,img, threshold):

        caffe_img = (img.copy() - 127.5) / 127.5
        origin_h, origin_w, ch = caffe_img.shape
        scales = tools.calculateScales(img)
        out = []
        t0 = time.time()
        # del scales[:4]

        for scale in scales:
            hs = int(origin_h * scale)
            ws = int(origin_w * scale)
            scale_img = cv2.resize(caffe_img, (ws, hs))
            input = scale_img.reshape(1, *scale_img.shape)
            ouput = self.Pnet.predict(input)  # .transpose(0,2,1,3) should add, but seems after process is wrong then.
            out.append(ouput)
        image_num = len(scales)
        rectangles = []
        for i in range(image_num):
            cls_prob = out[i][0][0][:, :,
                       1]  # i = #scale, first 0 select cls score, second 0 = batchnum, alway=0. 1 one hot repr
            roi = out[i][1][0]
            out_h, out_w = cls_prob.shape
            out_side = out_w
            if out_h>out_w:
                out_side = out_h
            #out_side = max(out_h, out_w)
            # print('calculating img scale #:', i)
            cls_prob = np.swapaxes(cls_prob, 0, 1)
            roi = np.swapaxes(roi, 0, 2)
            rectangle = tools.detect_face_12net(cls_prob, roi, out_side, 1 / scales[i], origin_w, origin_h,
                                                threshold[0])
            rectangles.extend(rectangle)
        rectangles = tools.NMS(rectangles, 0.7, 'iou')

        t1 = time.time()
        print('time for 12 net is: ', t1 - t0)

        if len(rectangles) == 0:
            return rectangles

        crop_number = 0
        out = []
        predict_24_batch = []
        for rectangle in rectangles:
            crop_img = caffe_img[int(rectangle[1]):int(rectangle[3]), int(rectangle[0]):int(rectangle[2])]
            scale_img = cv2.resize(crop_img, (24, 24))
            predict_24_batch.append(scale_img)
            crop_number += 1

        predict_24_batch = np.array(predict_24_batch)

        out = self.Rnet.predict(predict_24_batch)

        cls_prob = out[0]  # first 0 is to select cls, second batch number, always =0
        cls_prob = np.array(cls_prob)  # convert to numpy
        roi_prob = out[1]  # first 0 is to select roi, second batch number, always =0
        roi_prob = np.array(roi_prob)
        rectangles = tools.filter_face_24net(cls_prob, roi_prob, rectangles, origin_w, origin_h, threshold[1])
        t2 = time.time()
        print('time for 24 net is: ', t2 - t1)

        if len(rectangles) == 0:
            return rectangles

        crop_number = 0
        predict_batch = []
        for rectangle in rectangles:
            # print('calculating net 48 crop_number:', crop_number)
            crop_img = caffe_img[int(rectangle[1]):int(rectangle[3]), int(rectangle[0]):int(rectangle[2])]
            scale_img = cv2.resize(crop_img, (48, 48))
            predict_batch.append(scale_img)
            crop_number += 1

        predict_batch = np.array(predict_batch)

        output = self.Onet.predict(predict_batch)
        cls_prob = output[0]
        roi_prob = output[1]
        pts_prob = output[2]  # index
        rectangles = tools.filter_face_48net(cls_prob, roi_prob, pts_prob, rectangles, origin_w, origin_h, threshold[2])
        t3 = time.time()
        print('time for 48 net is: ', t3 - t2)

        return rectangles

    def rectangleDraw(self , rectangles, img):
        draw = img.copy()
        for rectangle in rectangles:
            if rectangle is not None:
                W = -int(rectangle[0]) + int(rectangle[2])
                H = -int(rectangle[1]) + int(rectangle[3])
                paddingH = 0.01 * W
                paddingW = 0.02 * H
                crop_img = img[int(rectangle[1] + paddingH):int(rectangle[3] - paddingH),
                           int(rectangle[0] - paddingW):int(rectangle[2] + paddingW)]
                crop_img = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                if crop_img is None:
                    continue
                if crop_img.shape[0] < 0 or crop_img.shape[1] < 0:
                    continue
                cv2.rectangle(draw, (int(rectangle[0]), int(rectangle[1])), (int(rectangle[2]), int(rectangle[3])),
                              (255, 0, 0), 1)
                crop_img = imutils.resize(crop_img, width=100)
                height, width = crop_img.shape[:2]
                temp_image = QImage(crop_img.flatten(), width, height, QImage.Format_RGB888)
                temp_pixmap = QPixmap.fromImage(temp_image)
                #加消息队列线程实现图片更新
                self.imgeLabel_0.setPixmap(temp_pixmap)
                cv2.imwrite('data/' + str(self.threadID) + 'test.jpg', crop_img)
        return draw