#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система логирования для PTT приложения
"""

import logging
import logging.handlers
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from config import LoggingConfig


class StructuredFormatter(logging.Formatter):
    """Форматтер для структурированных логов в JSON формате"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Добавляем дополнительные поля если есть
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Добавляем exception info если есть
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Форматтер для текстовых логов в человекочитаемом формате"""
    
    def __init__(self):
        super().__init__(
            fmt="[%(asctime)s] %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


class PTTLogger:
    """Основной класс логирования для PTT приложения"""
    
    def __init__(self, config: LoggingConfig):
        self.config = config
        self.logger = logging.getLogger("PTT")
        self._setup_logger()
    
    def _setup_logger(self):
        """Настройка логгера"""
        # Устанавливаем уровень логирования
        level = getattr(logging, self.config.level.upper())
        self.logger.setLevel(level)
        
        # Очищаем существующие хендлеры
        self.logger.handlers.clear()
        
        # Создаем хендлер для файла с ротацией
        log_path = Path(self.config.path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=self.config.max_size_mb * 1024 * 1024,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        
        # Создаем хендлер для консоли
        console_handler = logging.StreamHandler(sys.stderr)
        
        # Выбираем форматтер
        if self.config.format == "json":
            file_formatter = StructuredFormatter()
            console_formatter = StructuredFormatter()
        else:
            file_formatter = TextFormatter()
            console_formatter = TextFormatter()
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        # Добавляем хендлеры
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Отключаем propagation для избежания дублирования
        self.logger.propagate = False
    
    def _log_with_extra(self, level: int, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование с дополнительными полями"""
        if extra_fields:
            record = self.logger.makeRecord(
                name=self.logger.name,
                level=level,
                fn="",
                lno=0,
                msg=message,
                args=(),
                exc_info=None
            )
            record.extra_fields = extra_fields
            self.logger.handle(record)
        else:
            self.logger.log(level, message)
    
    def debug(self, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование на уровне DEBUG"""
        self._log_with_extra(logging.DEBUG, message, extra_fields)
    
    def info(self, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование на уровне INFO"""
        self._log_with_extra(logging.INFO, message, extra_fields)
    
    def warning(self, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование на уровне WARNING"""
        self._log_with_extra(logging.WARNING, message, extra_fields)
    
    def error(self, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование на уровне ERROR"""
        self._log_with_extra(logging.ERROR, message, extra_fields)
    
    def critical(self, message: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование на уровне CRITICAL"""
        self._log_with_extra(logging.CRITICAL, message, extra_fields)
    
    def exception(self, message: str, exc_info: Optional[Exception] = None, 
                  extra_fields: Optional[Dict[str, Any]] = None):
        """Логирование исключения с traceback"""
        if extra_fields:
            record = self.logger.makeRecord(
                name=self.logger.name,
                level=logging.ERROR,
                fn="",
                lno=0,
                msg=message,
                args=(),
                exc_info=exc_info
            )
            record.extra_fields = extra_fields
            self.logger.handle(record)
        else:
            self.logger.exception(message, exc_info=exc_info)
    
    def set_level(self, level: str):
        """Изменить уровень логирования"""
        if level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            self.config.level = level.upper()
            level_num = getattr(logging, level.upper())
            self.logger.setLevel(level_num)
            self.info(f"Log level changed to {level.upper()}")
        else:
            self.warning(f"Invalid log level: {level}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получить именованный логгер"""
        return logging.getLogger(f"PTT.{name}")


# Глобальный экземпляр логгера
def get_logger(name: str = "main") -> logging.Logger:
    """Получить логгер по имени"""
    return logging.getLogger(f"PTT.{name}")


def setup_logging(config: LoggingConfig) -> PTTLogger:
    """Настроить и вернуть основной логгер"""
    return PTTLogger(config)
