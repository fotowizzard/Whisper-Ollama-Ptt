#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер аудио для PTT приложения
"""

import numpy as np
import sounddevice as sd
import threading
import time
from typing import Optional, Callable, List, Deque
from collections import deque
from dataclasses import dataclass
from config import AudioConfig
from logging_config import get_logger


@dataclass
class AudioChunk:
    """Аудио чанк с метаданными"""
    data: np.ndarray
    timestamp: float
    duration: float


class CircularAudioBuffer:
    """Циклический буфер для аудио с ограничением размера"""
    
    def __init__(self, max_duration: float, sample_rate: int, channels: int):
        self.max_duration = max_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_samples = int(max_duration * sample_rate)
        self.buffer: Deque[AudioChunk] = deque()
        self.total_samples = 0
        self._lock = threading.Lock()
    
    def add_chunk(self, chunk: np.ndarray, duration: float):
        """Добавить аудио чанк в буфер"""
        with self._lock:
            # Создаем новый чанк
            audio_chunk = AudioChunk(
                data=chunk.copy(),
                timestamp=time.time(),
                duration=duration
            )
            
            # Добавляем в буфер
            self.buffer.append(audio_chunk)
            self.total_samples += len(chunk)
            
            # Удаляем старые чанки если превышен лимит
            while self.total_samples > self.max_samples and self.buffer:
                old_chunk = self.buffer.popleft()
                self.total_samples -= len(old_chunk.data)
    
    def get_all_audio(self) -> np.ndarray:
        """Получить все аудио из буфера и очистить его"""
        with self._lock:
            if not self.buffer:
                return np.array([], dtype=np.float32)
            
            # Собираем все чанки
            chunks = list(self.buffer)
            self.buffer.clear()
            self.total_samples = 0
            
            # Объединяем в один массив
            if len(chunks) == 1:
                return chunks[0].data
            
            return np.concatenate([chunk.data for chunk in chunks], axis=0)
    
    def get_duration(self) -> float:
        """Получить текущую длительность аудио в буфере"""
        with self._lock:
            return self.total_samples / self.sample_rate
    
    def is_empty(self) -> bool:
        """Проверить, пуст ли буфер"""
        with self._lock:
            return len(self.buffer) == 0
    
    def clear(self):
        """Очистить буфер"""
        with self._lock:
            self.buffer.clear()
            self.total_samples = 0


class AudioManager:
    """Менеджер аудио с поддержкой записи и буферизации"""
    
    def __init__(self, config: AudioConfig, logger=None):
        self.config = config
        self.logger = logger or get_logger("audio")
        
        # Состояние
        self._recording = threading.Event()
        self._stream: Optional[sd.InputStream] = None
        self._buffer = CircularAudioBuffer(
            max_duration=config.max_buffer_size,
            sample_rate=config.sample_rate,
            channels=config.channels
        )
        
        # Статистика
        self._stats = {
            "total_recordings": 0,
            "total_duration": 0.0,
            "peak_amplitude": 0.0,
            "last_recording_time": None
        }
        
        # Callback для уведомлений
        self._status_callback: Optional[Callable[[str], None]] = None
        
        self.logger.info(f"Audio manager initialized: {config.sample_rate}Hz, {config.channels}ch, "
                        f"max buffer: {config.max_buffer_size}s")
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """Установить callback для уведомлений о статусе"""
        self._status_callback = callback
    
    def _notify_status(self, status: str):
        """Уведомить о изменении статуса"""
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                self.logger.error(f"Status callback error: {e}")
    
    def _audio_callback(self, indata: np.ndarray, frames: int, 
                       time_info: dict, status: sd.CallbackFlags):
        """Callback для получения аудио данных"""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        if self._recording.is_set():
            # Берем первый канал если моно
            if self.config.channels == 1:
                chunk = indata[:, 0]
            else:
                chunk = indata.mean(axis=1)  # Микшируем в моно
            
            # Проверяем уровень сигнала
            amplitude = np.abs(chunk).max()
            if amplitude > self._stats["peak_amplitude"]:
                self._stats["peak_amplitude"] = amplitude
            
            # Добавляем в буфер
            duration = frames / self.config.sample_rate
            self._buffer.add_chunk(chunk, duration)
            
            self.logger.debug(f"Audio chunk: {frames} frames, duration: {duration:.3f}s, "
                            f"amplitude: {amplitude:.3f}")
    
    def start_recording(self) -> bool:
        """Начать запись"""
        if self._recording.is_set():
            self.logger.warning("Recording already in progress")
            return False
        
        try:
            self.logger.info("Starting audio recording")
            self._notify_status("recording")
            
            # Очищаем буфер
            self._buffer.clear()
            
            # Создаем поток
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=np.float32,
                callback=self._audio_callback,
                device=self.config.device,
                blocksize=int(self.config.sample_rate * self.config.chunk_duration)
            )
            
            self._stream.start()
            self._recording.set()
            
            # Обновляем статистику
            self._stats["total_recordings"] += 1
            self._stats["last_recording_time"] = time.time()
            
            self.logger.info("Audio recording started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self._notify_status("error")
            return False
    
    def stop_recording(self) -> Optional[np.ndarray]:
        """Остановить запись и вернуть собранное аудио"""
        if not self._recording.is_set():
            self.logger.warning("No recording in progress")
            return None
        
        try:
            self.logger.info("Stopping audio recording")
            self._notify_status("processing")
            
            # Останавливаем поток
            self._recording.clear()
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            
            # Получаем аудио из буфера
            audio = self._buffer.get_all_audio()
            
            if len(audio) == 0:
                self.logger.warning("No audio recorded")
                self._notify_status("no_audio")
                return None
            
            # Обновляем статистику
            duration = len(audio) / self.config.sample_rate
            self._stats["total_duration"] += duration
            
            self.logger.info(f"Recording stopped: {len(audio)} samples, {duration:.2f}s duration")
            self._notify_status("ready")
            
            return audio
            
        except Exception as e:
            self.logger.error(f"Failed to stop recording: {e}")
            self._notify_status("error")
            return None
    
    def is_recording(self) -> bool:
        """Проверить, идет ли запись"""
        return self._recording.is_set()
    
    def get_buffer_duration(self) -> float:
        """Получить текущую длительность аудио в буфере"""
        return self._buffer.get_duration()
    
    def get_peak_amplitude(self) -> float:
        """Получить пиковую амплитуду текущей записи"""
        return self._stats["peak_amplitude"]
    
    def get_stats(self) -> dict:
        """Получить статистику записи"""
        return self._stats.copy()
    
    def clear_stats(self):
        """Очистить статистику"""
        self._stats = {
            "total_recordings": 0,
            "total_duration": 0.0,
            "peak_amplitude": 0.0,
            "last_recording_time": None
        }
    
    def get_available_devices(self) -> list:
        """Получить список доступных аудио устройств"""
        try:
            devices = sd.query_devices()
            input_devices = []
            
            for i, device in enumerate(devices):
                if device['max_inputs'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': device['name'],
                        'channels': device['max_inputs'],
                        'sample_rate': device['default_samplerate']
                    })
            
            return input_devices
        except Exception as e:
            self.logger.error(f"Failed to query audio devices: {e}")
            return []
    
    def test_device(self, device_id: Optional[str] = None) -> bool:
        """Протестировать аудио устройство"""
        try:
            test_stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype=np.float32,
                device=device_id,
                blocksize=1024
            )
            test_stream.start()
            test_stream.stop()
            test_stream.close()
            return True
        except Exception as e:
            self.logger.error(f"Device test failed: {e}")
            return False
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            
            self._recording.clear()
            self._buffer.clear()
            
            self.logger.info("Audio manager cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()
