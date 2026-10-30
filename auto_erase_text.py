"""Frame-by-frame OCR and spatial inpainting; optional local dependencies."""
import argparse
from pathlib import Path
import subprocess
import sys

import cv2
import easyocr
import numpy as np


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    p = argparse.ArgumentParser()
    p.add_argument('source')
    p.add_argument('output')
    args = p.parse_args()
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        raise RuntimeError('영상 디코딩을 시작할 수 없습니다.')
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if width < 1 or height < 1 or not (1 <= fps <= 120):
        raise RuntimeError('영상 크기 또는 프레임 속도를 확인할 수 없습니다.')
    # Downloads EasyOCR model weights on first use. Korean + English is the default.
    reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'rawvideo', '-pix_fmt', 'bgr24',
           '-s', f'{width}x{height}', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
           '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', args.output]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            detections = reader.readtext(frame, detail=1, paragraph=False)
            mask = np.zeros((height, width), dtype=np.uint8)
            for points, _text, confidence in detections:
                if confidence >= 0.25:
                    cv2.fillPoly(mask, [np.asarray(points, dtype=np.int32)], 255)
            mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
            if np.any(mask):
                frame = cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
            proc.stdin.write(frame.tobytes())
            count += 1
    finally:
        cap.release()
        proc.stdin.close()
    if proc.wait() or count == 0:
        raise RuntimeError('자막 복원 영상 렌더에 실패했습니다.')
    print(f'처리 프레임: {count}. OCR은 모든 화면 글자를 대상으로 하며 결과 검수가 필요합니다.')


if __name__ == '__main__':
    main()
