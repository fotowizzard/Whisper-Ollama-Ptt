#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервис транскрипции на основе Whisper
"""

import numpy as np
import time
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from faster_whisper import WhisperModel
from config import WhisperConfig
from logging_config import get_logger


@dataclass
class TranscriptionResult:
    """Результат транскрипции"""
    text: str
    language: str
    confidence: float
    duration: float
    segments: List[Dict[str, Any]]
    processing_time: float


class WhisperService:
    """Сервис для работы с Whisper моделями"""
    
    def __init__(self, config: WhisperConfig, logger=None):
        self.config = config
        self.logger = logger or get_logger("whisper")
        self._model: Optional[WhisperModel] = None
        self._model_lock = threading.Lock()
        self._stats = {
            "total_transcriptions": 0,
            "total_processing_time": 0.0,
            "total_audio_duration": 0.0,
            "errors": 0,
            "last_used": None
        }
        
        self.logger.info(f"Initializing Whisper service: {config.model} on {config.device}")
        self._load_model()
    
    def _load_model(self) -> bool:
        """Загрузить Whisper модель"""
        try:
            with self._model_lock:
                if self._model is not None:
                    self.logger.info("Unloading existing Whisper model")
                    del self._model
                    self._model = None
                
                self.logger.info(f"Loading Whisper model: {self.config.model} "
                               f"on {self.config.device}/{self.config.compute_type}")
                
                self._model = WhisperModel(
                    self.config.model,
                    device=self.config.device,
                    compute_type=self.config.compute_type,
                    download_root=None,  # Используем кэш по умолчанию
                    local_files_only=False
                )
                
                self.logger.info("Whisper model loaded successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            return False
    
    def _validate_audio(self, audio: np.ndarray) -> bool:
        """Валидировать аудио данные"""
        if audio is None or len(audio) == 0:
            self.logger.warning("Empty audio data")
            return False
        
        if not isinstance(audio, np.ndarray):
            self.logger.warning("Audio data is not numpy array")
            return False
        
        if audio.dtype != np.float32:
            self.logger.warning(f"Audio dtype is {audio.dtype}, expected float32")
            return False
        
        # Проверяем, что аудио не слишком короткое
        min_duration = 0.1  # минимум 100ms
        if len(audio) < self.config.sample_rate * min_duration:
            self.logger.warning(f"Audio too short: {len(audio)/self.config.sample_rate:.3f}s")
            return False
        
        return True
    
    def transcribe(self, audio: np.ndarray, language: Optional[str] = None) -> Optional[TranscriptionResult]:
        """Транскрибировать аудио"""
        start_time = time.time()
        
        try:
            # Валидация аудио
            if not self._validate_audio(audio):
                return None
            
            # Проверяем модель
            if self._model is None:
                self.logger.error("Whisper model not loaded")
                return None
            
            # Определяем язык если не указан
            if language is None:
                language = self.config.language
            
            # Параметры транскрипции
            transcription_params = {
                "language": language,
                "vad_filter": self.config.vad_filter,
                "beam_size": self.config.beam_size,
                "best_of": self.config.best_of,
                "temperature": self.config.temperature,
                "condition_on_previous_text": False,
                "initial_prompt": None,
                "word_timestamps": False,
                "compression_ratio_threshold": 2.4,
                "log_prob_threshold": -1.0,  # Исправлено: logprob_threshold -> log_prob_threshold
                "no_speech_threshold": 0.6
            }
            
            self.logger.debug(f"Starting transcription with params: {transcription_params}")
            
            # Выполняем транскрипцию
            segments, info = self._model.transcribe(audio, **transcription_params)
            
            # Обрабатываем результат
            text_parts = []
            all_segments = []
            
            for segment in segments:
                text_parts.append(segment.text.strip())
                all_segments.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "end": segment.end,
                    "words": getattr(segment, 'words', [])
                })
            
            # Объединяем текст
            final_text = " ".join(text_parts).strip()
            
            # Вычисляем время обработки
            processing_time = time.time() - start_time
            audio_duration = len(audio) / self.config.sample_rate
            
            # Создаем результат
            result = TranscriptionResult(
                text=final_text,
                language=info.language,
                confidence=getattr(info, 'language_probability', 0.0),
                duration=audio_duration,
                segments=all_segments,
                processing_time=processing_time
            )
            
            # Обновляем статистику
            self._stats["total_transcriptions"] += 1
            self._stats["total_processing_time"] += processing_time
            self._stats["total_audio_duration"] += audio_duration
            self._stats["last_used"] = time.time()
            
            self.logger.info(f"Transcription completed: {len(final_text)} chars, "
                           f"duration: {audio_duration:.2f}s, "
                           f"processing: {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            self._stats["errors"] += 1
            return None
    
    def transcribe_with_retry(self, audio: np.ndarray, language: Optional[str] = None, 
                             max_retries: int = 2) -> Optional[TranscriptionResult]:
        """Транскрибировать с повторными попытками"""
        for attempt in range(max_retries + 1):
            try:
                result = self.transcribe(audio, language)
                if result is not None:
                    return result
                
                if attempt < max_retries:
                    self.logger.warning(f"Transcription attempt {attempt + 1} failed, retrying...")
                    time.sleep(1.0)  # Пауза перед повтором
                    
            except Exception as e:
                self.logger.error(f"Transcription attempt {attempt + 1} error: {e}")
                if attempt < max_retries:
                    time.sleep(1.0)
        
        self.logger.error(f"All {max_retries + 1} transcription attempts failed")
        return None
    
    def change_model(self, model_name: str, device: Optional[str] = None, 
                    compute_type: Optional[str] = None) -> bool:
        """Изменить модель Whisper"""
        try:
            # Обновляем конфигурацию
            old_model = self.config.model
            old_device = self.config.device
            old_compute = self.config.compute_type
            
            self.config.model = model_name
            if device:
                self.config.device = device
            if compute_type:
                self.config.compute_type = compute_type
            
            # Загружаем новую модель
            if self._load_model():
                self.logger.info(f"Model changed from {old_model} to {model_name}")
                return True
            else:
                # Восстанавливаем старую конфигурацию
                self.config.model = old_model
                self.config.device = old_device
                self.config.compute_type = old_compute
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to change model: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получить информацию о текущей модели"""
        if self._model is None:
            return {"status": "not_loaded"}
        
        try:
            return {
                "status": "loaded",
                "model": self.config.model,
                "device": self.config.device,
                "compute_type": self.config.compute_type,
                "model_size": getattr(self._model, 'model_size', 'unknown'),
                "is_multilingual": getattr(self._model, 'is_multilingual', True)
            }
        except Exception as e:
            self.logger.error(f"Failed to get model info: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику использования"""
        stats = self._stats.copy()
        if stats["total_transcriptions"] > 0:
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["total_transcriptions"]
            stats["avg_audio_duration"] = stats["total_audio_duration"] / stats["total_transcriptions"]
        else:
            stats["avg_processing_time"] = 0.0
            stats["avg_audio_duration"] = 0.0
        
        return stats
    
    def clear_stats(self):
        """Очистить статистику"""
        self._stats = {
            "total_transcriptions": 0,
            "total_processing_time": 0.0,
            "total_audio_duration": 0.0,
            "errors": 0,
            "last_used": None
        }
    
    def reload_model(self) -> bool:
        """Перезагрузить модель"""
        self.logger.info("Reloading Whisper model")
        return self._load_model()
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            with self._model_lock:
                if self._model is not None:
                    del self._model
                    self._model = None
                self.logger.info("Whisper service cleaned up")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки"""
        self.cleanup()
