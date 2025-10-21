from PyQt5 import QtWidgets, QtCore, QtGui
from difflib import SequenceMatcher
import asyncio
from googletrans import Translator
translator = Translator()


class TranslateWorker(QtCore.QThread):
    translated = QtCore.pyqtSignal(list, list)
    result_ready = QtCore.pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        self.texts = []
        self.pending = False

        self.previous_combined_text = ""
        self.previous_texts = []
        self.previous_translated_text = []

        self.force_refresh = False

    def receive_texts(self, texts):
        self.texts = texts
        self.pending = True

    def translate_batch(self, jp_list):
        async def _do_batch():
            t = Translator(service_urls=['translate.googleapis.com'])
            # Bulk‐translate in one go:
            return await t.translate(jp_list, src="ja", dest="en")
        return asyncio.run(_do_batch())

    def translate_single(self, txt):
        async def _do_one():
            t = Translator(service_urls=['translate.googleapis.com'])
            return await t.translate(txt, src="ja", dest="en")
        return asyncio.run(_do_one())
    
    def force_translate(self):
        self.force_refresh = True

    def run(self):
        while True:
            if self.pending:
                # Build the combined JP block for similarity checking
                # combined_text = "\n".join(self.texts or [])
                combined_text = [t for t in self.texts if t.strip()]
                joined_prev = "\n".join(sorted(self.previous_texts))
                joined_cur  = "\n".join(sorted(combined_text))
                print("----- [TextDiff] Comparing Texts -----", flush=True)
                print("[Previous JP Text]:\n", self.previous_combined_text, flush=True)
                print("[Current JP Text]:\n", combined_text, flush=True)
                similarity = SequenceMatcher(None, joined_prev, joined_cur).ratio()
                print("Similarity:", similarity)

                # If nothing really changed, reuse last translations
                if similarity >= 0.9 and len(combined_text) <= len(self.previous_combined_text) and not self.force_refresh:
                    print("[TextDiff] Same text — reusing previous result.", flush=True)
                    self.translated.emit(self.texts, self.previous_translated_text)
                    self.pending = False
                else:
                    self.force_refresh = False
                    print("[TextDiff] Different text - translating...")
                    # Prepare a clean list of strings (no None)
                    jp_list = [t if t is not None else "" for t in self.texts]
                    print(*jp_list, sep=", ")

                    try:
                        batch = self.translate_batch(jp_list)
                        en_list = [res.text for txt, res in zip(jp_list, batch) if txt.strip()]
                    except Exception as e:
                        print("[TranslateWorker] Batch translation failed:", e, flush=True)
                        en_list = []
                        for txt in jp_list:
                            if not txt.strip():
                                en_list.append("")
                            else:
                                try:
                                    single = self.translate_single(txt)
                                    en_list.append(single.text)
                                except Exception as e2:
                                    print("[TranslateWorker] Single translation failed:", e2, flush=True)
                                    en_list.append("Translation Error")

                    # Remember & emit
                    print("[TranslateWorker] Emitting result:", flush=True)
                    print("JP:", jp_list, flush=True)
                    print("EN:", en_list, flush=True)

                    self.previous_combined_text   = combined_text
                    self.previous_texts = combined_text.copy()
                    self.previous_translated_text = en_list
                    self.translated.emit(jp_list, en_list)
                    self.pending = False

            self.msleep(100)


    def shutdown_now(self):
        print("[Exit] Shutting down TranslateWorker.")
        self.quit()