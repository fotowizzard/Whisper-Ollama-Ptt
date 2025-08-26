#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация приложения PTT
"""

import os
import yaml
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class AudioConfig:
    """Конфигурация аудио"""
    sample_rate: int = 16000
    channels: int = 1
    device: Optional[str] = None
    max_buffer_size: int = 30  # секунд
    chunk_duration: float = 0.1  # секунд

    def __post_init__(self):
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            raise ValueError(f"Unsupported sample rate: {self.sample_rate}")
        if self.channels not in [1, 2]:
            raise ValueError(f"Unsupported channels: {self.channels}")


@dataclass
class WhisperConfig:
    """Конфигурация Whisper"""
    model: str = "small"
    device: str = "auto"
    compute_type: str = "int8"
    language: str = "ru"
    sample_rate: int = 16000  # Частота дискретизации для аудио
    vad_filter: bool = False
    beam_size: int = 1
    best_of: int = 1
    temperature: float = 0.0

    def __post_init__(self):
        if self.model not in ["tiny", "base", "small", "medium", "large", "large-v3"]:
            raise ValueError(f"Unsupported Whisper model: {self.model}")
        if self.device not in ["auto", "cpu", "cuda"]:
            raise ValueError(f"Unsupported device: {self.device}")
        if self.compute_type not in ["int8", "int16", "float16", "float32"]:
            raise ValueError(f"Unsupported compute type: {self.compute_type}")


@dataclass
class OllamaConfig:
    """Конфигурация Ollama"""
    url: str = "http://127.0.0.1:11434/api/generate"
    model: str = "qwen2.5:7b-instruct"
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0

    def __post_init__(self):
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive: {self.timeout}")
        if self.max_retries < 0:
            raise ValueError(f"Max retries must be non-negative: {self.max_retries}")


@dataclass
class TextInjectionConfig:
    """Конфигурация вставки текста"""
    autopaste: bool = True
    type_fallback: bool = True
    paste_delay: float = 0.05
    type_delay: float = 0.0
    restore_clipboard: bool = True


@dataclass
class LoggingConfig:
    """Конфигурация логирования"""
    level: str = "INFO"
    path: str = "ptt.log"
    max_size_mb: int = 10
    backup_count: int = 3
    format: str = "json"  # json или text

    def __post_init__(self):
        if self.level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Unsupported log level: {self.level}")
        if self.format not in ["json", "text"]:
            raise ValueError(f"Unsupported log format: {self.format}")


@dataclass
class AppConfig:
    """Основная конфигурация приложения"""
    ptt_key: str = "f9"
    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    text_injection: TextInjectionConfig = field(default_factory=TextInjectionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Дополнительные настройки
    enable_sound_notifications: bool = True
    enable_visual_feedback: bool = True
    auto_start_with_windows: bool = False
    check_updates: bool = False

    def __post_init__(self):
        if not self.ptt_key:
            raise ValueError("PTT key cannot be empty")

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Создать конфигурацию из переменных окружения"""
        config = cls()
        
        # Основные настройки
        if os.environ.get("PTT_KEY"):
            config.ptt_key = os.environ["PTT_KEY"]
        
        # Аудио
        if os.environ.get("SAMPLE_RATE"):
            config.audio.sample_rate = int(os.environ["SAMPLE_RATE"])
        if os.environ.get("CHANNELS"):
            config.audio.channels = int(os.environ["CHANNELS"])
        if os.environ.get("AUDIO_DEVICE"):
            config.audio.device = os.environ["AUDIO_DEVICE"]
        
        # Whisper
        if os.environ.get("WHISPER_MODEL"):
            config.whisper.model = os.environ["WHISPER_MODEL"]
        if os.environ.get("WHISPER_DEVICE"):
            config.whisper.device = os.environ["WHISPER_DEVICE"]
        if os.environ.get("WHISPER_COMPUTE"):
            config.whisper.compute_type = os.environ["WHISPER_COMPUTE"]
        if os.environ.get("WHISPER_LANGUAGE"):
            config.whisper.language = os.environ["WHISPER_LANGUAGE"]
        if os.environ.get("WHISPER_SAMPLE_RATE"):
            config.whisper.sample_rate = int(os.environ["WHISPER_SAMPLE_RATE"])
        # Синхронизируем sample_rate с аудио конфигурацией
        config.whisper.sample_rate = config.audio.sample_rate
        
        # Ollama
        if os.environ.get("OLLAMA_URL"):
            config.ollama.url = os.environ["OLLAMA_URL"]
        if os.environ.get("OLLAMA_MODEL"):
            config.ollama.model = os.environ["OLLAMA_MODEL"]
        if os.environ.get("OLLAMA_TIMEOUT"):
            config.ollama.timeout = float(os.environ["OLLAMA_TIMEOUT"])
        
        # Вставка текста
        if os.environ.get("AUTOPASTE"):
            config.text_injection.autopaste = os.environ["AUTOPASTE"] == "1"
        if os.environ.get("TYPE_FALLBACK"):
            config.text_injection.type_fallback = os.environ["TYPE_FALLBACK"] == "1"
        
        # Логирование
        if os.environ.get("LOG_PATH"):
            config.logging.path = os.environ["LOG_PATH"]
        if os.environ.get("LOG_LEVEL"):
            config.logging.level = os.environ["LOG_LEVEL"].upper()
        
        return config

    @classmethod
    def from_file(cls, file_path: str) -> 'AppConfig':
        """Загрузить конфигурацию из файла"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.suffix.lower() == '.yaml' or file_path.suffix.lower() == '.yml':
                data = yaml.safe_load(f)
            elif file_path.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {file_path.suffix}")
        
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Создать конфигурацию из словаря"""
        config = cls()
        
        # Обновляем основные поля
        for key, value in data.items():
            if hasattr(config, key) and not key.startswith('_'):
                if isinstance(value, dict):
                    # Для вложенных конфигураций
                    sub_config = getattr(config, key)
                    for sub_key, sub_value in value.items():
                        if hasattr(sub_config, sub_key):
                            setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(config, key, value)
        
        return config

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать конфигурацию в словарь"""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_'):
                if hasattr(value, 'to_dict'):
                    result[key] = value.to_dict()
                else:
                    result[key] = value
        return result

    def save_to_file(self, file_path: str):
        """Сохранить конфигурацию в файл"""
        file_path = Path(file_path)
        data = self.to_dict()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.suffix.lower() == '.yaml' or file_path.suffix.lower() == '.yml':
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            elif file_path.suffix.lower() == '.json':
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Unsupported config file format: {file_path.suffix}")

    def validate(self) -> bool:
        """Валидировать конфигурацию"""
        try:
            self.__post_init__()
            self.audio.__post_init__()
            self.whisper.__post_init__()
            self.ollama.__post_init__()
            self.logging.__post_init__()
            return True
        except Exception:
            return False


# Глобальный экземпляр конфигурации
CONFIG = AppConfig.from_env()
