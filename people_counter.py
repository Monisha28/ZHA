from tracker.centroidtracker import CentroidTracker
from tracker.trackableobject import TrackableObject
from imutils.video import FPS
from imutils.video import VideoStream
import numpy as np
import argparse
import imutils
import time
import dlib
import cv2

ap = argparse.ArgumentParser()
ap.add_argument("-p", "--prototxt", required=True,
	help="path to Caffe 'deploy' prototxt file")
ap.add_argument("-m", "--model", required=True,
	help="path to Caffe pre-trained model")
ap.add_argument("-i", "--input", type=str,
	help="path to optional input video file")
ap.add_argument("-o", "--output", type=str,
	help="path to optional output video file")
ap.add_argument("-c", "--confidence", type=float, default=0.4,
	help="minimum probability to filter weak detections")
ap.add_argument("-s", "--skip-frames", type=int, default=30,
	help="# of skip frames between detections")
args = vars(ap.parse_args())


CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
	"bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
	"dog", "horse", "motorbike", "person", "pottedplant", "sheep",
	"sofa", "train", "tvmonitor"]
print("loading model...")
net = cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])

# reference to the webcam
if not args.get("input", False):
	print("starting video stream...")
	vs = VideoStream(src=0).start()
	time.sleep(2.0)
#reference to the video file
else:
	print("opening video file...")
	vs = cv2.VideoCapture(args["input"])

writer = None
#frame dimensions 
W = None
H = None
ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
trackers = []
trackableObjects = {}
totalFrames = 0
totalDown = 0
totalUp = 0

fps = FPS().start()

while True:
	frame = vs.read()
	frame = frame[1] if args.get("input", False) else frame
	if args["input"] is not None and frame is None:
		break

	frame = imutils.resize(frame, width=500)
	rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

	# if the frame dimensions are empty, set them
	if W is None or H is None:
		(H, W) = frame.shape[:2]

	if args["output"] is not None and writer is None:
		fourcc = cv2.VideoWriter_fourcc(*"MJPG")
		writer = cv2.VideoWriter(args["output"], fourcc, 30,
			(W, H), True)

	status = "Waiting"
	rects = []
	if totalFrames % args["skip_frames"] == 0:
		status = "Detecting"
		trackers = []
		#obtain the detections
		blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
		net.setInput(blob)
		detections = net.forward()
		# loop over the detections
		for i in np.arange(0, detections.shape[2]):
			confidence = detections[0, 0, i, 2]
			if confidence > args["confidence"]:
				idx = int(detections[0, 0, i, 1])
				if CLASSES[idx] != "person":
					continue

				box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
				(startX, startY, endX, endY) = box.astype("int")

				tracker = dlib.correlation_tracker()
				rect = dlib.rectangle(startX, startY, endX, endY)
				tracker.start_track(rgb, rect)
				trackers.append(tracker)
	else:
		for tracker in trackers:
			status = "Tracking"
			tracker.update(rgb)
			pos = tracker.get_position()
			startX = int(pos.left())
			startY = int(pos.top())
			endX = int(pos.right())
			endY = int(pos.bottom())
			rects.append((startX, startY, endX, endY))

	#horizontal line in the center of the frame
	cv2.line(frame, (0, H // 2), (W, H // 2), (0, 255, 255), 2)
	objects = ct.update(rects)

	for (objectID, centroid) in objects.items():
		to = trackableObjects.get(objectID, None)
		if to is None:
			to = TrackableObject(objectID, centroid)
		else:
			y = [c[1] for c in to.centroids]
			direction = centroid[1] - np.mean(y)
			to.centroids.append(centroid)
			
			#counter up nd down
			if not to.counted:
				if direction < 0 and centroid[1] < H // 2:
					totalUp += 1
					to.counted = True

				elif direction > 0 and centroid[1] > H // 2:
					totalDown += 1
					to.counted = True

		trackableObjects[objectID] = to
		text = "Num {}".format(objectID)
		cv2.putText(frame, text, (centroid[0] - 10, centroid[1] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
		cv2.circle(frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)

	info = [
		("Out", totalUp),
		("In", totalDown),
		("Status", status),
	]
	# loop over the info tuples and draw them on frame
	for (i, (k, v)) in enumerate(info):
		text = "{}: {}".format(k, v)
		cv2.putText(frame, text, (10, H - ((i * 20) + 20)),
			cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
	if writer is not None:
		writer.write(frame)
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(1) & 0xFF
	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break
	totalFrames += 1
	fps.update()
fps.stop()
# print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
# print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
if writer is not None:
	writer.release()

if not args.get("input", False):
	vs.stop()
else:
	vs.release()
cv2.destroyAllWindows()

