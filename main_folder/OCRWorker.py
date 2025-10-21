from PyQt5 import QtWidgets, QtCore, QtGui
from concurrent.futures import ThreadPoolExecutor
import cv2
import re
import mss
import time
import imagehash
import numpy as np
from PIL import Image
import hashlib
import easyocr
from manga_ocr import MangaOcr
from craft_text_detector import Craft, craft_utils
import torch
print("CUDA Available:", torch.cuda.is_available())
print("Device:", torch.device("cuda" if torch.cuda.is_available() else "cpu"))

import nltk
nltk.download('words')
from nltk.corpus import words
english_vocab = set(words.words())

mo = MangaOcr()
easyocr_reader = easyocr.Reader(['en'], gpu=True)
craft = Craft(output_dir="output", crop_type="box", cuda=torch.cuda.is_available())
craft_utils.adjustResultCoordinates = lambda polys, ratio_w, ratio_h, ratio_net=2: np.array([
    np.array(poly) * np.array([ratio_w * ratio_net, ratio_h * ratio_net]) for poly in polys if poly is not None
])


class OCRWorker(QtCore.QThread):
    result_ready = QtCore.pyqtSignal(list)
    mini_coords = QtCore.pyqtSignal(list)

    def __init__(self, selector, interval=500):
        super().__init__()

        self.selector = selector
        self.interval = interval  # milliseconds
        self.running = True
        # self.previous_hash = None
        self.last_processed_hash = None  # Only updated after OCR/translation
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.last_emit_time = 0  # track latest displayed frame

        self.last_hash      = None
        self.hash_threshold = 5
        self.force_refresh  = False
        self.skip_next_run = False
        self.ocr_cache = {}

        self.latest_text = []

        self.last_submit_timestamp = 0

    def run(self):
        while self.running:
            
            if self.skip_next_run:
                self.skip_next_run = False
                self.msleep(self.interval)
                continue

            bbox = self.selector.get_bbox()
            start_hash_time = time.time()
            image = self.capture_screen(bbox)
            # print(f"[{threading.current_thread().name}] [Timing] Screen capture took {time.time() - start_hash_time:.4f} seconds", flush=True)

            # Compare current screenshot with previous using perceptual hash
            start_hash_time = time.time()
            current_hash = imagehash.phash(image)
            # hash_diff = abs(current_hash - self.previous_hash) if self.previous_hash else 999
            hash_diff = abs(current_hash - self.last_processed_hash) if self.last_processed_hash else 999
            # print("[Timing] pHash comparison took {:.4f} seconds".format(time.time() - start_hash_time), flush=True)
            # print("[pHash] Difference from previous frame:", hash_diff, flush=True)

            if self.last_processed_hash is not None and hash_diff <= 1 and not self.force_refresh_flag:
                print("Hashing here")
                self.msleep(self.interval)
                continue

            self.previous_hash = current_hash
            self.force_refresh_flag = False
            timestamp = time.time()
            self.last_submit_timestamp = timestamp
            try:
                self.executor.submit(self.process_frame, image.copy(), timestamp)
            except RuntimeError:
                print("[Thread] Executor is shut down — exiting run loop.")
                break

            # Process screenshot asynchronously
            # self.executor.submit(self.process_frame, image.copy(), timestamp)
            self.msleep(self.interval)

    # def force_translate_now(self):
    #     gc.collect()
    #     try:
    #         if torch.cuda.is_available():
    #             torch.cuda.empty_cache()
    #     except RuntimeError as e:
    #         print("[Warning] Failed to clear CUDA cache:", e)

    #     print("[Force] Manual translation refresh triggered.", flush=True)

    #     # Capture a fresh screenshot
    #     bbox = self.selector.get_bbox()
    #     image = self.capture_screen(bbox)

    #     # Run OCR from scratch
    #     boxes = self.detect_text_regions(image)
    #     crops = self.crop_text_regions(image, boxes)
    #     ocr_text = self.extract_japanese_text_from_regions(crops)

    #     combined_text = "\n".join(ocr_text)
    #     print("[Force] OCR text:\n", combined_text)

    #     def translate_task():
    #         try:
    #             result = translator.translate(combined_text, src="ja", dest="en")
    #             translated = result.text if result and result.text else "Translation Error"
    #         except Exception as e:
    #             print("[Force Translate] Error during translation:", e)
    #             translated = "Translation Error"

    #         self.result_ready.emit(ocr_text)

    #     threading.Thread(target=translate_task, daemon=True).start()


    def force_capture(self):
        bbox = self.selector.get_bbox()
        image = self.capture_screen(bbox)
        self.force_refresh = True
        self.skip_next_run = True
        timestamp = time.time()
        try:
            self.executor.submit(self.process_frame, image.copy(), timestamp)
        except RuntimeError:
            print("[Thread] Executor is shut down — exiting run loop.")


    def process_frame(self, image, timestamp):
        if timestamp < self.last_submit_timestamp:
            return
        
        # 1) frame-level pHash skip

        pil_img = image.convert("RGB")
        frame_hash = imagehash.phash(pil_img)
        if (self.last_hash is not None
            and abs(frame_hash - self.last_hash) <= self.hash_threshold
            and not self.force_refresh):
            return
        self.last_hash     = frame_hash

        # 2) detect & crop in-memory
        frame_bgr  = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        raw_boxes  = self.detect_text_regions(frame_bgr)                  # [(x1,y1,x2,y2),…]
        crops      = self.crop_text_regions(frame_bgr, raw_boxes)         # [(np.ndarray,(x,y,w,h)),…]

        # 3) prepare placeholders for EXACTLY len(crops)
        jp_texts   = [None] * len(crops)
        coords_out = [None] * len(crops)
        to_ocr     = []   # will hold (index, PIL_image, coords, hsh)

        for idx, (crop_bgr, (x, y, w, h)) in enumerate(crops):
            hsh = hashlib.sha1(crop_bgr.tobytes()).hexdigest()
            coords = (x, y, w, h)

            if (hsh in self.ocr_cache) and not self.force_refresh:
                jp_texts[idx]   = self.ocr_cache[hsh]
                coords_out[idx] = coords
                print("Image seen before")
            else:
                pil = Image.fromarray(cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB))
                to_ocr.append((idx, pil, coords, hsh))

        print("1. Force Refresh:", self.force_refresh)
        self.force_refresh = False
        print("2. Force Refresh:", self.force_refresh)

        # 4) OCR the genuinely new ones and slot them back in place
        if to_ocr:
            extracted = self.extract_japanese_text_from_regions(to_ocr)
        for idx, jp, coord, hsh in extracted:
            self.ocr_cache[hsh] = jp
            jp_texts[idx]       = jp
            coords_out[idx]     = coord

        # 5) now filter out any blanks and emit — order is intact
        final_jps   = []
        final_coords = []
        for jp, coords in zip(jp_texts, coords_out):
            if jp:              # skip empty OCR results if you like
                final_jps.append(jp)
                final_coords.append(coords)

        # self.mini_coords.emit(final_coords)
        # self.result_ready.emit(final_jps)

        paired = list(zip(final_coords, final_jps))
        paired.sort(key=lambda item: (item[0][1], item[0][0]))  # sort by y then x
        if paired:
            sorted_coords, sorted_jps = zip(*paired)
        else:
            sorted_coords, sorted_jps = [], []
        
        self.mini_coords.emit(list(sorted_coords))
        self.result_ready.emit(list(sorted_jps))

    def capture_screen(self, bbox):
        with mss.mss() as sct:
            monitor = {
                "top": int(bbox[1]),
                "left": int(bbox[0]),
                "width": int(bbox[2] - bbox[0]),
                "height": int(bbox[3] - bbox[1])
            }
            sct_img = sct.grab(monitor)
            return Image.frombytes("RGB", sct_img.size, sct_img.rgb)

    # Can speed up using DBNet over craft-text-detector
    # def detect_text_regions(self, image):
    #     image.save("temp.png")
    #     prediction = craft.detect_text("temp.png")
    #     return [box for box in prediction["boxes"] if box is not None and len(box) == 4]

    def detect_text_regions(self, image):
        # print("[Debug] detect_text_regions() called", flush=True)
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        prediction = craft.detect_text(image_cv)
        
        boxes = [box for box in prediction["boxes"] if box is not None and len(box) == 4]
        # print(f"[Craft] Detected {len(boxes)} boxes")
        return boxes



    def crop_text_regions(self, image, bboxes):
        # if os.path.exists("cropped_images"):
        #     shutil.rmtree("cropped_images")
        # os.makedirs("cropped_images")

        def polygon_to_bbox(poly):
            points = np.array(poly, dtype=np.int32)
            x_min, y_min = points.min(axis=0)
            x_max, y_max = points.max(axis=0)
            return [x_min, y_min, x_max, y_max]

        def merge_boxes(boxes, x_thresh, y_thresh):
            def boxes_are_close(a, b):
                return not (
                    b[2] < a[0] - x_thresh or
                    b[0] > a[2] + x_thresh or
                    b[3] < a[1] - y_thresh or
                    b[1] > a[3] + y_thresh
                )

            # Track bounding boxes of entire groups instead of each inner box
            group_bounds = []  # merged representative of each group
            groups = []

            for box in boxes:
                matched = False
                for i, bound in enumerate(group_bounds):
                    if boxes_are_close(box, bound):
                        groups[i].append(box)
                        # Update bounding box for future comparisons
                        x1 = min(bound[0], box[0])
                        y1 = min(bound[1], box[1])
                        x2 = max(bound[2], box[2])
                        y2 = max(bound[3], box[3])
                        group_bounds[i] = [x1, y1, x2, y2]
                        matched = True
                        break
                if not matched:
                    groups.append([box])
                    group_bounds.append(box[:])  # make a copy

            merged = group_bounds  # each bound is already the merged box
            return merged


        start_merge = time.time()
        boxes = [polygon_to_bbox(b) for b in bboxes]
        boxes = merge_boxes(boxes, x_thresh=10, y_thresh=1)
        # print("[Timing] Merging boxes took {:.4f} seconds".format(time.time() - start_merge))


        start_merge = time.time()
        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        cropped = []
        global caption_boxes
        caption_boxes = []
        bbox = self.selector.get_bbox()  # (left, top, right, bottom)
        left, top, right, bottom = bbox
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            
            # Adjust coordinates by adding offset of capture box
            x1_global = x1 + left
            y1_global = y1 + top
            x2_global = x2 + left
            y2_global = y2 + top

            width = x2_global - x1_global
            height = y2_global - y1_global

            # mini_box = MiniCaptionBox(x1_global, y1_global, width, height, text="")
            # mini_box.make_click_through()
            # caption_boxes.append(mini_box)

            crop = image_cv[y1:y2, x1:x2]
            # pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            # pil.save(f"cropped_images/cropped_{i}.png")
            # cropped.append((pil, box))
            cropped.append((crop, (x1_global, y1_global, width, height)))
        # print("[Timing] Cropped boxes took {:.4f} seconds".format(time.time() - start_merge))
        return cropped

    def extract_japanese_text_from_regions(self, crops):
        local_boxes = []
        results = []
        for (idx, image, (x1_global, y1_global, width, height), hsh) in crops:
            np_img = np.array(image.convert('RGB'))
            easy_text = " ".join(easyocr_reader.readtext(np_img, detail=0)).strip()
            print("[EasyOCR] easy_text:", easy_text)

            # if re.search(r'[A-Za-z]{4,}', easy_text):
            #     print("[Filter] EasyOCR detected English-like text, skipping")
            #     # results.append("")
            #     continue
            if contains_english_word(easy_text):
                print("[Filter] EasyOCR detected real English word, skipping")
                continue

            text = mo(image) or ""
            print("[MangaOCR] Raw output:", text)

            jp_chars = re.findall(r'[\u3000-\u30FF\u4E00-\u9FFF]', text)
            en_chars = re.findall(r'[A-Za-z]', text)
            # print("[Filter] JP count:", len(jp_chars), "EN count:", len(en_chars))

            if len(jp_chars) >= 2 and len(en_chars) <= 1:
                results.append((idx, text, (x1_global, y1_global, width, height), hsh))

                # local_boxes.append(BoxInfo(x1_global, y1_global, width, height, jp_text=text, en_text=""))
                local_boxes.append((x1_global, y1_global, width, height))
                # mini_box = MiniCaptionBox(x1_global, y1_global, width, height)
                # mini_box.make_click_through()
                # caption_boxes.append(mini_box)
            else:
                print("[Filter] Skipped (didn't pass JP/EN threshold)")

        # print(f"[OCR] Extracted {len(results)} Japanese segments")
        return results
    
    def shutdown_now(self):
        print("[Mini][Exit] Shutting down OCRWorker immediately.")
        self.running = False
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.quit()


def contains_english_word(text, min_valid_words=2):
    tokens = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())  # only 2+ letter words
    matches = [word for word in tokens if word in english_vocab]
    return len(matches) >= min_valid_words