#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper + Ollama Push‑to‑Talk (Windows)
MVP, местно, офлайн. Основа: опыт и знания модели. Внешние источники не использовались.

Функционал:
- Глобальная клавиша push‑to‑talk (по умолчанию F9): зажали — запись, отпустили — распознавание.
- ASR: faster‑whisper (модель Whisper), язык ru.
- Пост‑обработка: локальный Ollama (по умолчанию qwen2.5:7b-instruct).
- Вставка текста в активное окно: сначала Ctrl+V из буфера; если не сработало — по символам.
- Трей‑иконка: включение/выключение автопостинга, выход.

Установка (Windows, Python 3.10+):
1) Установите зависимости:
   pip install -U faster-whisper sounddevice keyboard pyperclip requests pystray pillow
2) Убедитесь, что Ollama запущен:
   ollama serve
   ollama pull qwen2.5:7b-instruct
3) Запуск:
   python whisper_ollama_ptt_windows.py
4) Автозапуск: создайте ярлык скрипта в %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup

Сборка в .exe (опционально):
   pip install pyinstaller
   pyinstaller --noconsole --onefile whisper_ollama_ptt_windows.py

Ограничения MVP:
- Нет VAD и нет оверлея с аудиограммой (можно добавить позже).
- Запись ведётся только пока зажата клавиша PTT (F9).
"""

import io
import os
import sys
import time
import json
import queue
import threading
import traceback
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import requests

from faster_whisper import WhisperModel

# Трей
import pystray
from PIL import Image, ImageDraw


# =====================
# Конфигурация
# =====================
@dataclass
class Config:
    # Горячая клавиша PTT (используем простую клавишу для надёжной обработки press/release)
    PTT_KEY: str = os.environ.get("PTT_KEY", "f9")

    # Аудио
    SAMPLE_RATE: int = int(os.environ.get("SAMPLE_RATE", 16000))
    CHANNELS: int = int(os.environ.get("CHANNELS", 1))
    DEVICE: str | None = os.environ.get("AUDIO_DEVICE")  # None = default input

    # Whisper
    WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "small")  # "small"/"medium"/"large-v3" и т.п.
    WHISPER_DEVICE: str = os.environ.get("WHISPER_DEVICE", "auto")  # "auto"/"cpu"/"cuda"
    WHISPER_COMPUTE: str = os.environ.get("WHISPER_COMPUTE", "int8")  # для CPU: int8; для CUDA: float16

    # Ollama
    OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
    OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    OLLAMA_TIMEOUT: float = float(os.environ.get("OLLAMA_TIMEOUT", 10.0))

    # Вставка
    AUTOPASTE: bool = os.environ.get("AUTOPASTE", "1") == "1"
    TYPE_FALLBACK: bool = os.environ.get("TYPE_FALLBACK", "1") == "1"

    # Логи
    LOG_PATH: str = os.environ.get("LOG_PATH", os.path.join(os.path.dirname(__file__), "ptt.log"))


CFG = Config()


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(CFG.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Последний шанс — в stderr
        sys.stderr.write(line)


# =====================
# Иконка трея
# =====================

def make_icon(active: bool) -> Image.Image:
    # Простая 16x16 иконка: кружок зелёный = активен, серый = неактивен
    size = (64, 64)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (60, 200, 60, 255) if active else (160, 160, 160, 255)
    d.ellipse([8, 8, 56, 56], fill=color)
    return img


# =====================
# Основное приложение
# =====================
class PTTApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.icon: pystray.Icon | None = None
        self.autopaste = cfg.AUTOPASTE
        self._recording = threading.Event()
        self._audio_buf = []  # список numpy-массивов
        self._stream: sd.InputStream | None = None
        self._whisper = None
        self._lock = threading.Lock()
        self._load_whisper_model()
        self._setup_tray()

    # Whisper загрузка
    def _load_whisper_model(self):
        log(f"Loading Whisper model: {self.cfg.WHISPER_MODEL} on {self.cfg.WHISPER_DEVICE}/{self.cfg.WHISPER_COMPUTE}")
        self._whisper = WhisperModel(
            self.cfg.WHISPER_MODEL,
            device=self.cfg.WHISPER_DEVICE,
            compute_type=self.cfg.WHISPER_COMPUTE,
        )

    # Трей
    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: f"Auto‑paste: {'ON' if self.autopaste else 'OFF'}",
                self._toggle_autopaste,
            ),
            pystray.MenuItem("Exit", self._on_exit),
        )
        self.icon = pystray.Icon("PTT", make_icon(True), "PTT Whisper+Ollama", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def _toggle_autopaste(self, icon, item):
        self.autopaste = not self.autopaste
        log(f"AUTOPASTE set to {self.autopaste}")
        # Обновить title
        if self.icon:
            self.icon.title = f"PTT (autopaste={'ON' if self.autopaste else 'OFF'})"
            self.icon.icon = make_icon(True)

    def _on_exit(self, icon, item):
        log("Exit requested")
        os._exit(0)

    # Аудио callback
    def _audio_cb(self, indata, frames, time_info, status):
        if status:
            log(f"Audio status: {status}")
        # indata: float32, shape (frames, channels)
        if self._recording.is_set():
            # берём первый канал
            chunk = indata[:, 0].copy()
            self._audio_buf.append(chunk)

    # PTT управление
    def start_recording(self):
        if self._recording.is_set():
            return
        log("Start recording")
        self._audio_buf = []
        self._recording.set()
        self._stream = sd.InputStream(
            samplerate=self.cfg.SAMPLE_RATE,
            channels=self.cfg.CHANNELS,
            dtype="float32",
            callback=self._audio_cb,
            device=self.cfg.DEVICE,
        )
        self._stream.start()
        if self.icon:
            self.icon.icon = make_icon(True)
            self.icon.title = "PTT: listening… (hold F9)"

    def stop_recording(self):
        if not self._recording.is_set():
            return
        log("Stop recording")
        self._recording.clear()
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None
        # Собираем аудио и обрабатываем в воркере
        if not self._audio_buf:
            if self.icon:
                self.icon.title = "PTT: no audio"
            return
        audio = np.concatenate(self._audio_buf, axis=0)
        threading.Thread(target=self._process_audio, args=(audio,), daemon=True).start()

    def _process_audio(self, audio: np.ndarray):
        try:
            # ASR
            if self.icon:
                self.icon.title = "PTT: transcribing…"
            text = self._transcribe(audio)
            log(f"Whisper raw: {text}")
            # LLM пост-обработка
            clean = self._postprocess_with_ollama(text)
            log(f"Postprocessed: {clean}")
            # Вставка
            if self.autopaste:
                self._inject_text(clean)
                if self.icon:
                    self.icon.title = "PTT: inserted"
            else:
                # Копируем в буфер, но не вставляем
                self._to_clipboard(clean)
                if self.icon:
                    self.icon.title = "PTT: copied to clipboard"
        except Exception as e:
            log(f"Error in _process_audio: {e}\n{traceback.format_exc()}")
            if self.icon:
                self.icon.title = "PTT: error (see log)"
        finally:
            # вернуть иконку
            if self.icon:
                self.icon.icon = make_icon(True)

    def _transcribe(self, audio: np.ndarray) -> str:
        # faster-whisper принимает numpy с Fs=16000 float32
        # Параметры подобраны для скорости/качества; при необходимости отрегулировать
        segments, info = self._whisper.transcribe(
            audio=audio,
            language="ru",
            vad_filter=False,
            beam_size=1,
            best_of=1,
            temperature=0.0,
        )
        out = []
        for seg in segments:
            out.append(seg.text)
        return " ".join(out).strip()

    def _postprocess_with_ollama(self, text: str) -> str:
        # Если Ollama не доступен — вернуть исходный текст
        prompt = (
            "Ты редактор русского текста. Исправь пунктуацию, регистр, явные оговорки. "
            "Сохраняй смысл, НЕ перефразируй лишнего. Удали междометия типа 'э-э', 'ну'. "
            "Верни только финальный текст без пояснений.\n\nТекст:\n" + text
        )
        try:
            r = requests.post(
                self.cfg.OLLAMA_URL,
                json={"model": self.cfg.OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=self.cfg.OLLAMA_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            # Ответ Ollama в поле "response"
            cleaned = data.get("response", "").strip()
            return cleaned or text
        except Exception as e:
            log(f"Ollama error: {e}")
            return text

    def _to_clipboard(self, text: str):
        try:
            pyperclip.copy(text)
        except Exception as e:
            log(f"Clipboard error: {e}")

    def _inject_text(self, text: str):
        # 1) через буфер + Ctrl+V
        try:
            old_clip = None
            try:
                old_clip = pyperclip.paste()
            except Exception:
                old_clip = None
            pyperclip.copy(text)
            time.sleep(0.05)
            keyboard.send("ctrl+v")
            time.sleep(0.05)
            # восстановить буфер
            if old_clip is not None:
                pyperclip.copy(old_clip)
            return
        except Exception as e:
            log(f"Paste failed: {e}")
        # 2) по символам
        if self.cfg.TYPE_FALLBACK:
            try:
                keyboard.write(text, delay=0.0)
            except Exception as e:
                log(f"Type fallback failed: {e}")

    # Главный цикл: хуки клавиатуры
    def run(self):
        log(f"PTT ready. Hold {self.cfg.PTT_KEY.upper()} to speak.")
        keyboard.on_press_key(self.cfg.PTT_KEY, lambda e: self.start_recording())
        keyboard.on_release_key(self.cfg.PTT_KEY, lambda e: self.stop_recording())
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass


def main():
    try:
        app = PTTApp(CFG)
        app.run()
    except Exception as e:
        log(f"Fatal: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()