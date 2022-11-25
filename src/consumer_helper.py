import cv2
import dlib
import json
import boto3
import subprocess
import numpy as np
import imageio as iio
import multiprocessing
from multiprocessing import Pool


def interrupt_handler(sig_int, context):
    global running
    running = False
    pass


def pixelate(frame, blocks=3):
    # borrowed from https://pyimagesearch.com/2020/04/06/blur-and-anonymize-faces-with-opencv-and-python/
    (h, w) = frame.shape[:2]

    x_steps = np.linspace(0, w, blocks + 1, dtype="int")
    y_steps = np.linspace(0, h, blocks + 1, dtype="int")

    for i in range(1, len(y_steps)):
        for j in range(1, len(x_steps)):
            # compute the starting and ending (x, y)-coordinates
            # for the current block
            start_x = x_steps[j - 1]
            start_y = y_steps[i - 1]
            end_x = x_steps[j]
            end_y = y_steps[i]
            # extract the ROI using NumPy array slicing, compute the
            # mean of the ROI, and then draw a rectangle with the
            # mean RGB values over the ROI in the original image
            roi = frame[start_y:end_y, start_x:end_x]
            (B, G, R) = [int(x) for x in cv2.mean(roi)[:3]]
            cv2.rectangle(frame, (start_x, start_y), (end_x, end_y), (B, G, R), -1)
    return frame


def censor(frames, job):
    censored_frames = []
    frame_count = 0
    print(frames)
    raw_frames = []

    for frame in iio.v3.imiter(frames, extension=".mkv"):
        raw_frames.append(frame)

    for frame in raw_frames:
        base_image = frame.copy()

        bounding_box = job["FaceSearchResponse"][0]["DetectedFace"]["BoundingBox"]

        h, w = frame.shape[:2]
        left = int(bounding_box["Left"] * w) - 20
        top = int(bounding_box["Top"] * h) - 20
        right = int(left + (bounding_box["Width"] * w)) + 20
        bottom = int(top + (bounding_box["Height"] * h)) + 20

        if frame_count == 0:
            # Initialize the tracker
            tracker = dlib.correlation_tracker()
            tracker.start_track(base_image, dlib.rectangle(left=left, top=top, right=right, bottom=bottom))

        frame_count += 1

        tracking_quality = tracker.update(base_image)

        if tracking_quality >= 5:
            tracked_position = tracker.get_position()

            t_left = int(tracked_position.left())
            t_top = int(tracked_position.top())
            t_right = int(tracked_position.left()) + int(tracked_position.width())
            t_bottom = int(tracked_position.bottom()) + int(tracked_position.height())

            censored_face = pixelate(frame[t_top:t_bottom, t_left:t_right])
            base_image[t_top:t_bottom, t_left:t_right] = censored_face
            censored_frames.append(base_image)
        pass

    import os
    os.remove(job["InputInformation"]["KinesisVideo"]["FragmentNumber"] + ".mkv")

    iio.v3.imwrite(
        (job["InputInformation"]["KinesisVideo"]["FragmentNumber"] + "censored.mkv"),
        censored_frames, extension=".mkv", fps=30
    )

    return job["InputInformation"]["KinesisVideo"]["FragmentNumber"] + "censored.mkv"


def put_media(file, local_stream):
    print("Uploading to kinesis video")
    upload = subprocess.call(
        [
            'bash',
            "./upload_file.sh",
            file,
            local_stream + "-censored",
        ])
    import os
    os.remove(file)


def save_video(frames, job, video_stream):
    local_session = boto3.Session(region_name='us-east-1')

    fragment_num = job["InputInformation"]["KinesisVideo"]["FragmentNumber"]

    video_name = fragment_num + ".mkv"
    put_key = video_stream + "-censored/" + video_name

    print("Starting saving video")
    # try:
    #     iio.v3.imwrite(video_name, frames, extension='.mkv', fps=30)
    # except Exception as e:
    #     print(e)
    
    print("Uploading Video")
    put_media(frames, video_stream)


def download_and_censor(local_vid, job):
    local_session = boto3.Session(region_name='us-east-1')
    kinesis_video = local_session.client('kinesisvideo')
    endpoint = kinesis_video.get_data_endpoint(
        StreamARN=local_vid,
        APIName='GET_MEDIA'
    )["DataEndpoint"]

    kinesis_video = local_session.client('kinesis-video-media', endpoint_url=endpoint)

    fragment = None
    try:
        fragment = kinesis_video.get_media(
            StreamARN=local_vid,
            StartSelector={
                'StartSelectorType': 'FRAGMENT_NUMBER',
                'AfterFragmentNumber': job["InputInformation"]["KinesisVideo"]["FragmentNumber"]
            }
        )
    except Exception as e:
        print(e)
        pass

    if fragment is not None:
        frames = []
        stuff = fragment["Payload"].read()
        print(stuff)
        try:
            # frames = list(iio.v3.imiter(stuff, extension='.mkv'))
            with open((job["InputInformation"]["KinesisVideo"]["FragmentNumber"] + ".mkv"), "wb") as download:
                download.write(stuff)
        except Exception as e:
            print(e)
            pass

        return job["InputInformation"]["KinesisVideo"]["FragmentNumber"] + ".mkv"
        
        
async def do_download_and_censor(job):
    video_file = download_and_censor(job["InputInformation"]["KinesisVideo"]["StreamArn"], job)
    censored = censor(video_file, job)
    video_stream = job["InputInformation"]["KinesisVideo"]["StreamArn"].split('/')[2]
    save_video(censored, job, ctx["video_stream"])
    
    return 


"""
def match_track_shards():
    global data_stream, video_stream, storage, session, running

    pool = Pool()
    m = multiprocessing.Manager()
    q = m.Queue()
    
    while running:
        job = q.get()
        video_file = download_and_censor(job["InputInformation"]["KinesisVideo"]["StreamArn"], job)
        censored = censor(video_file, job)
        save_video(censored, job, ctx["video_stream"], ctx["storage"])

        import gc
        gc.collect()

    pool.terminate()
    pool.join()
    # pass
"""